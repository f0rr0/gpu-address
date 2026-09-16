"""Small GPU-native affine-scan address tagger."""

import torch
from torch import nn
from torch.nn import functional as F

from .schema import LABELS

HIDDEN = 128
LAYERS = 2
ARCHITECTURE = "ordered-byte-conv32-scan128-v3-seven"


def affine_scan(gate: torch.Tensor, candidate: torch.Tensor) -> torch.Tensor:
    """Inclusive scan for state[t] = gate[t] * state[t-1] + candidate[t]."""
    stride = 1
    while stride < gate.shape[1]:
        next_gate = gate[:, stride:] * gate[:, :-stride]
        next_candidate = candidate[:, stride:] + gate[:, stride:] * candidate[:, :-stride]
        gate = torch.cat((gate[:, :stride], next_gate), 1)
        candidate = torch.cat((candidate[:, :stride], next_candidate), 1)
        stride *= 2
    return candidate


class ScanLayer(nn.Module):
    def __init__(self):
        super().__init__()
        self.gate = nn.Linear(HIDDEN, HIDDEN)
        self.candidate = nn.Linear(HIDDEN, HIDDEN)
        self.combine = nn.Linear(HIDDEN * 2, HIDDEN)
        with torch.no_grad():
            self.gate.bias.copy_(torch.linspace(0, 4, HIDDEN))

    def forward(self, value: torch.Tensor, valid: torch.Tensor) -> torch.Tensor:
        gate = torch.sigmoid(self.gate(value))
        candidate = (1 - gate) * torch.tanh(self.candidate(value))
        gate = torch.where(valid, gate, torch.ones_like(gate))
        candidate = candidate * valid
        forward = affine_scan(gate, candidate)
        backward = affine_scan(gate.flip(1), candidate.flip(1)).flip(1)
        return torch.tanh(value + self.combine(torch.cat((forward, backward), -1))) * valid


class Tagger(nn.Module):
    allowed: torch.Tensor
    start_allowed: torch.Tensor

    def __init__(self, gap_features=False, *, architecture=None):
        super().__init__()
        if architecture != ARCHITECTURE:
            raise ValueError(f"Unsupported model architecture: {architecture!r}")
        self.config = dict(architecture=ARCHITECTURE, gap_features=gap_features)
        self.embedding = nn.Embedding(257, 32, padding_idx=0)
        self.char_conv = nn.Conv1d(32, 32, 3, padding=1)
        self.project = nn.Linear(64, HIDDEN)
        self.local = nn.Parameter(torch.empty(5, HIDDEN))
        self.local_bias = nn.Parameter(torch.zeros(HIDDEN))
        self.layers = nn.ModuleList(ScanLayer() for _ in range(LAYERS))
        self.output = nn.Linear(HIDDEN, len(LABELS))
        self.transitions = nn.Parameter(torch.zeros(len(LABELS), len(LABELS)))
        self.start = nn.Parameter(torch.zeros(len(LABELS)))
        self.end = nn.Parameter(torch.zeros(len(LABELS)))
        nn.init.normal_(self.embedding.weight, std=0.08)
        with torch.no_grad():
            self.embedding.weight[0].zero_()
        nn.init.normal_(self.local, std=0.15)
        allowed = torch.zeros(len(LABELS), len(LABELS))
        start_allowed = torch.zeros(len(LABELS))
        for j, tag in enumerate(LABELS):
            if tag.startswith("I-"):
                start_allowed[j] = -10000
                for i, previous in enumerate(LABELS):
                    if previous not in ("B-" + tag[2:], tag):
                        allowed[i, j] = -10000
        self.register_buffer("allowed", allowed)
        self.register_buffer("start_allowed", start_allowed)

    def forward(self, byte_ids: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        present = byte_ids.ne(0).unsqueeze(-1)
        embedded = self.embedding(byte_ids) * present
        shape = embedded.shape
        ordered = self.char_conv(embedded.reshape(-1, shape[2], 32).transpose(1, 2))
        embedded = (embedded + torch.relu(ordered.transpose(1, 2).reshape(shape))) * present
        mean = (embedded * present).sum(2) / present.sum(2).clamp(min=1)
        maximum = embedded.masked_fill(~present, -10000).max(2).values
        maximum = torch.where(present.any(2), maximum, torch.zeros_like(maximum))
        valid = torch.arange(byte_ids.shape[1], device=byte_ids.device)[None, :]
        valid = (valid < lengths.to(byte_ids.device)[:, None]).unsqueeze(-1)
        value = torch.tanh(self.project(torch.cat((mean, maximum), -1))) * valid
        channels = value.transpose(1, 2)
        kernel = self.local.transpose(0, 1).unsqueeze(1)
        local = F.conv1d(channels, kernel, padding=2, groups=HIDDEN).transpose(1, 2)
        value = torch.tanh(value + local + self.local_bias) * valid
        for layer in self.layers:
            value = layer(value, valid)
        return self.output(value)

    def loss(
        self,
        emissions: torch.Tensor,
        gold: torch.Tensor,
        lengths: torch.Tensor,
        weights: torch.Tensor | None = None,
    ) -> torch.Tensor:
        lengths = lengths.to(emissions.device)
        transitions = self.transitions + self.allowed
        starts = self.start + self.start_allowed
        score = starts[gold[:, 0]] + emissions[:, 0].gather(1, gold[:, :1]).squeeze(1)
        alpha = starts + emissions[:, 0]
        for t in range(1, emissions.shape[1]):
            active = t < lengths
            step = transitions[gold[:, t - 1], gold[:, t]] + emissions[:, t].gather(
                1, gold[:, t : t + 1]
            ).squeeze(1)
            score = score + step * active
            updated = torch.logsumexp(alpha.unsqueeze(2) + transitions, dim=1) + emissions[:, t]
            alpha = torch.where(active.unsqueeze(1), updated, alpha)
        last = gold.gather(1, (lengths - 1).unsqueeze(1)).squeeze(1)
        score = score + self.end[last]
        partition = torch.logsumexp(alpha + self.end, dim=1)
        losses = (partition - score) / lengths
        return (losses if weights is None else losses * weights).mean()

    def decode(self, emissions: torch.Tensor, lengths: torch.Tensor) -> list[list[int]]:
        transitions = self.transitions + self.allowed
        score = self.start + self.start_allowed + emissions[:, 0]
        history = []
        for t in range(1, emissions.shape[1]):
            best, previous = (score.unsqueeze(2) + transitions).max(1)
            updated = best + emissions[:, t]
            score = torch.where((t < lengths.to(emissions.device)).unsqueeze(1), updated, score)
            history.append(previous.cpu())
        last = (score + self.end).argmax(1).cpu().tolist()
        paths = []
        for b, length in enumerate(lengths.tolist()):
            path = [last[b]]
            for t in range(length - 2, -1, -1):
                path.append(int(history[t][b, path[-1]]))
            paths.append(path[::-1])
        return paths
