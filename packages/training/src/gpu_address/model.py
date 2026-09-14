"""Byte CNN, bidirectional GRU and BIO-constrained CRF."""

import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

from .schema import LABELS


class Tagger(nn.Module):
    allowed: torch.Tensor
    start_allowed: torch.Tensor

    def __init__(self, hidden=144, layers=2, gap_features=False):
        super().__init__()
        self.config = dict(hidden=hidden, layers=layers, gap_features=gap_features)
        self.embedding = nn.Embedding(257, 32, padding_idx=0)
        self.char_conv = nn.Conv1d(32, 32, 3, padding=1)
        self.project = nn.Linear(64, 96)
        self.gru = nn.GRU(
            96,
            hidden,
            layers,
            batch_first=True,
            bidirectional=True,
            dropout=0.1 if layers > 1 else 0,
        )
        self.dropout = nn.Dropout(0.1)
        self.output = nn.Linear(hidden * 2, len(LABELS))
        self.transitions = nn.Parameter(torch.zeros(len(LABELS), len(LABELS)))
        self.start = nn.Parameter(torch.zeros(len(LABELS)))
        self.end = nn.Parameter(torch.zeros(len(LABELS)))
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
        embedding = self.embedding(byte_ids)
        shape = embedding.shape
        local = self.char_conv(embedding.reshape(-1, shape[2], 32).transpose(1, 2))
        embedding = embedding + torch.relu(local.transpose(1, 2).reshape(shape))
        mean = (embedding * present).sum(2) / present.sum(2).clamp(min=1)
        maximum = embedding.masked_fill(~present, -10000).max(2).values
        maximum = torch.where(present.any(2), maximum, torch.zeros_like(maximum))
        features = torch.tanh(self.project(torch.cat([mean, maximum], -1)))
        packed = pack_padded_sequence(
            features, lengths.cpu(), batch_first=True, enforce_sorted=True
        )
        recurrent, _ = self.gru(packed)
        recurrent, _ = pad_packed_sequence(
            recurrent, batch_first=True, total_length=byte_ids.shape[1]
        )
        return self.output(self.dropout(recurrent))

    def loss(
        self, emissions: torch.Tensor, gold: torch.Tensor, lengths: torch.Tensor
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
        return ((partition - score) / lengths).mean()

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
