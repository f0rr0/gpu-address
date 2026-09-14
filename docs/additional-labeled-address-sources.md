# Additional labeled address sources

Checked September 14, 2026. This is a source shortlist, not a completed ingestion or label-quality audit. Our importer currently uses bounded portions of two 2017 libpostal address archives and Senzing's custom archive. We have not exhausted the available labeled data.

Update: [the executed acquisition and quality audit](address-source-quality-audit.md) records which sources were acquired, filtered, quarantined, or unavailable, and the resulting model comparison. The shortlist below preserves the original source assessment.

| Source | Available material | Fit and remaining work |
| --- | --- | --- |
| [Senzing v1.2 training archives](https://github.com/Senzing/libpostal-data#training-data) | Six archives covering addresses, places, ways, GeoPlanet, OpenAddresses, and custom examples | First choice for extending our existing tag-compatible importer. We currently sample only its custom archive. Read through the files and sample by geography; do not assume archive prefixes are representative. |
| [Original libpostal training data](https://github.com/openvenues/libpostal#training-data) | Separate tagged places, streets, postcode/admin combinations, and UK addresses, beyond our two sampled address archives | My hypothesis: place/admin examples could reduce country/city/state confusion. Keep their mixture capped so full street-address parsing does not regress. |
| [Deepparse worldwide-addresses](https://huggingface.co/datasets/deepparse/worldwide-addresses) | Publisher reports over 750 million annotated examples; 240 country-code configurations, over 100 languages, Parquet | Convenient targeted acquisition. Uses ten tags and removes punctuation: map labels, audit lost distinctions, and restore realistic formatting. Libpostal-derived, so overlapping provenance is expected. |
| [Earlier Deepparse address dataset](https://github.com/GRAAL-Research/deepparse-address-data) | 100,000 clean training examples per country for 20 countries; incomplete-address sets; another 41 countries in its zero-shot split | Country-specific pools include 26,075 India examples. Audit mapping and deduplicate against existing data. If repurposing a published evaluation split for our training, explicitly retire it as evaluation. |
| [Neural Chinese Address Parsing](https://github.com/leodotnet/neural-chinese-address-parsing) | Published train/dev/test files plus English and Chinese annotation guidelines | Candidate for different annotation conventions and Chinese component boundaries. Review schema and dataset reuse terms before ingestion; do not assume it covers Taiwan's conventions. |

## Structured sources we can turn into labeled strings

These are not annotated free-form input corpora. They provide component records from which a renderer can preserve known field spans:

- [Australia G-NAF](https://data.gov.au/data/dataset/geocoded-national-address-file-g-naf): national address records; potentially useful for Australian address structures. Review component mapping and its published data terms.
- [France Base Adresse Nationale](https://adresse.data.gouv.fr/outils/telechargements): national and departmental CSV downloads. Its data also flows into OpenAddresses, so a different download URL does not guarantee new underlying addresses.

## Acquisition order

1. Audit small samples from the unused Senzing place/way/GeoPlanet archives and the weak-country Deepparse partitions.
2. Prefer original libpostal-compatible labels where available; the reduced Deepparse schema cannot recover distinctions it discarded.
3. Count unique originals, streets, cities, countries, scripts, and fields. Remove existing normalized-string overlaps and preserve geographic groups across variants.
4. Build one expanded training version and compare the unchanged architecture against `continuation-100k`. Evaluate both aggregate and country/field regressions.

These sources can expand training substantially, but several descend from the same OSM/OpenAddresses/libpostal pipeline. They must not be counted as independent gold merely because different projects distribute them. Retain a separately annotated real-input evaluation set. Country partitioning makes targeted sampling practical; there is no need to train on the entire corpus for the next experiment.
