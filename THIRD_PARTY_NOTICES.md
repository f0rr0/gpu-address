# Third-party notices

Our original source code and documentation are MIT licensed (© 2026 Sid Jain).
This does not relicense upstream datasets or remove their conditions. The model
is distributed with the source notices below, **not as an unrestricted MIT-only
artifact**. No raw training corpus or competitor model is included in the package.
No upstream organization endorses this project.

## G-NAF — Australian training source

Incorporates or developed using G-NAF © Geoscape Australia licensed by the
Commonwealth of Australia under the Open Geo-coded National Address File (G-NAF)
End User Licence Agreement.

We used Dylan Hogg's conversion of the August 2022 release, shard 0, pinned at
`fe77dbd9d7ab802f074d5286a4b016a4813ed8a4`. Structured fields were rendered into
addresses, filtered, deduplicated, mapped to our seven labels and used for training.

- [Pinned source and attribution](https://huggingface.co/datasets/dylanhogg/gnaf-2022/blob/fe77dbd9d7ab802f074d5286a4b016a4813ed8a4/README.md)
- [Official source and EULA resources](https://data.gov.au/data/dataset/geocoded-national-address-file-g-naf)

The source terms are based on CC BY 4.0 with an additional mailing condition:
open G-NAF must not be used to generate an address or compilation of addresses
for sending mail unless each address's ability to receive mail has been verified
using a secondary source. Preserve this notice with the weights. This parser
does not perform that verification and must not be represented as doing so.

## Structured Multinational Address Data / worldwide-addresses

Marouane Yassine and David Beauchemin, *Structured Multinational Address Data*
(2026), distributed by Deepparse/GRAAL Research under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
[Pinned dataset card](https://huggingface.co/datasets/deepparse/worldwide-addresses/blob/cb61e5e49db87f8c3586b5494149f612460f8992/README.md).

The dataset derives from libpostal's tagged training data; it is not independent
of the sources below. We filtered to seven countries and eligible language
metadata, remapped labels, reviewed subsets, deduplicated, split groups and
applied case augmentation. Source labels are not independently verified truth.

## libpostal, Senzing, OpenStreetMap and OpenAddresses lineage

- [libpostal](https://github.com/openvenues/libpostal), Al Barrentine and
  contributors (MIT code), provided tagged address corpora and methodological
  inspiration. Its code license is not a blanket license for all source data.
- [Senzing libpostal-data](https://github.com/Senzing/libpostal-data) supplied
  tagged training material and public diagnostic data (v1.2.0). Its repository
  is Apache-2.0; upstream data retains its own terms. Our model does not bundle
  Senzing's model or runtime.
- © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright).
  OpenStreetMap data is available under the Open Database License (ODbL).
- [OpenAddresses](https://openaddresses.io) aggregates sources with varying
  attribution and reuse terms; see its [source catalog](https://github.com/openaddresses/openaddresses).
- Yahoo GeoPlanet-derived formatted place data is present in the inherited
  libpostal/Senzing lineage; see the upstream distribution's source notices.

The inherited corpora do not preserve complete row-level original-provider
licensing metadata. These notices preserve known lineage; they are not a legal
certification of every upstream record or a claim that all data is MIT licensed.
Redistributing the raw training data requires a separate source-level review.

## Evaluation and inspiration

The [GeoSearch address-parsing benchmark](https://github.com/zhengcongyin/Geocoding-Address-Parsing-Benchmark)
is evaluation-only. The release includes aggregate scores and a reproduction
script, not its input corpus. Competitor packages retain their respective terms.

[GPU Lexer](https://github.com/vercel-labs/gpu-lexer) and
[GPU Time](https://github.com/arikchakma/gpu-time) inspired the small-model,
local-browser approach. They are not runtime dependencies. Development tools
such as TypeScript and PyTorch retain their own licenses.

## Website components

The website uses [shadcn/ui](https://github.com/shadcn-ui/ui) components (MIT,
copyright shadcn) and [Dither Kit](https://tripwire.sh/dither-kit) chart and gradient components
by ripgrim / Boring Software, installed from its published registry on September
17, 2026. Dither Kit's CLI declares MIT, but its public source repository does not
currently supply a license file. Those vendored chart files are upstream code,
not covered by our original-code copyright claim; confirm their redistribution
terms before publishing the website. These website dependencies are not part of
the gpu-postal runtime or its advertised package size.

The website uses [gpu-lexer](https://github.com/vercel-labs/gpu-lexer)
(MIT, copyright Shu Ding) for code syntax highlighting. It is not included in
the gpu-postal runtime.
