# Address annotation policy

## Seven-field model contract (16 September 2026)

The trained/browser contract now has seven fields: `street_address`, `locality`,
`city`, `district`, `state`, `postcode`, `country`. District remains distinct from
city and locality; it may contain a city. Fields are optional, never inferred.
Keep original detailed source annotations intact. The detailed conventions below
continue to describe source evidence; `schema.seven_fields` derives model targets.

- Premises, property numbers, roads, units, floors, entrances, stairs, PO boxes and
  explicit landmark relations project to `street_address`.
- `suburb` and `city_district` project to `locality`; `state_district` to `district`.
- City, state, postcode and country retain their roles.
- Adjacent equal fields merge across whitespace, commas or semicolons only, retaining
  the exact intervening source text. Unrelated words never get swallowed by a merge.
- Category/world-region expressions are outside the seven address fields.
- The legacy `island` → locality and `country_region` → state mapping is a coarse
  compatibility convention, not geographic equivalence or a newly validated rule.
  Fresh ambiguous island/region annotations require contextual review.

Fresh annotations use the seven fields directly. Keep complete landmark phrases
together when their role is clear; do not reclassify a delivery city as a landmark
merely because a relation phrase appears elsewhere. Legacy projection cannot resolve
all such contextual cases. Every model output still carries source offsets; this is
not a reformatter or a geocoder. Old 41-tag weights are incompatible with 15-tag
models; explicit encoder-only transfer initializes a fresh output/CRF head.

This is the contract for training admission and natural-address review. Annotate only
what is present in the input; never infer a missing component from source
metadata or geographic knowledge.

## Span contract

- Annotate the smallest exact, contiguous substring that expresses one field.
- `start` is inclusive and `end` exclusive; offsets are Unicode code-point
  offsets in Python. `raw` must equal `text[start:end]` byte-for-byte.
- Include meaningful internal punctuation and whitespace inside a component
  (`12-14`, `St.`, `Apt. 4`), but exclude separators shared with neighbors.
- A road name immediately followed by its parenthesized alternative name is one
  `road` span, including the parentheses. This requires an attested alias relation;
  do not merge two distinct roads or parenthesized locality/premises content.
- Keep repeated occurrences as separate components, in input order.
- Use only fields in `schema.py`; genuinely non-address text is `O`. An unresolved
  address component is not background: flag the record for adjudication rather than
  accepting an incomplete annotation.
- `house_number` identifies a property; `house` is a named building/property.
  Use `unit` for apartment/suite/room and `level` for floor/storey; do not
  duplicate a number across fields.
- Include an explicit property-locator prefix in its span (`No 1`, `Plot 216`,
  `Survey No 11/1`, `Km 9`); do not silently discard the designation as `O`.
- Preserve an explicit postal-code designator with its code (`Cp 36040`,
  `C.P. 36040`, `CEP45113-500`) inside `postcode`. This is extraction, not an
  instruction to add prefixes to outgoing mail. [Correos de México](https://www.correosdemexico.com.mx/AcercaDe/Documents/formatoSPM-CCC-007.pdf)
  and [Correios](https://www.correios.com.br/Plone/enviar/encomendas/arquivo/nacional/guia-de-enderecamento.pdf)
  establish these postal designators; unrelated lookalike abbreviations need context.

## Premise-led addresses and coarse source fields

An address line (sometimes called “street address” on forms) is not the same
thing as our `road` field. A flat, wing, floor and named building can form valid
address-like input without a road, property number, city or postcode. Parsing
such input does not certify postal deliverability. Do not reject it or invent
missing components. This applies worldwide, not only in India.

Indian evidence supports separating premises from thoroughfares:
[UIDAI's address-certificate instructions](https://www.uidai.gov.in/images/commdoc/26_JAN_2023_Aadhaar_List_of_documents_English.pdf)
distinguish house/building/apartment from street/road/lane;
[Melissa's India format](https://www.melissa.com/global-address-formatting-examples/india)
groups floor, subpremises, subbuilding and building separately from thoroughfare.
These are structured conventions, not proof that informal forms use consistent names.
[Libpostal's label definitions](https://github.com/openvenues/libpostal#parser-labels)
likewise distinguish road, building, secondary unit and floor.

Our annotation convention is `unit` for an explicitly designated secondary
wing/block/tower within premises; `house` for a named building; `level` for floor.
Do not use `entrance` or `staircase` unless the text identifies one. A block that
denotes an area rather than a subbuilding needs locality adjudication. This is a
documented schema choice, not a claim that every postal system calls wings units.
Keep adjacent apartment/wing identifiers together when they form one secondary
designation. Preserve separate occurrences when separated by address delimiters.

For `1001 B wing, 10th floor, Rustomjee orinana`, our contextual interpretation is
`unit: 1001 B wing`, `level: 10th floor`, `house: Rustomjee orinana`, with no `road`.
Preserve that spelling. The bare number is interpreted as an apartment from the
surrounding wing/floor/building cues; do not generalize “four digits means flat”.
This user-provided example is a development fixture, never unseen evaluation data.

Source `StreetName` or `StreetNumber` fields can contain composite address lines.
Keep the raw row and source tags; a mismatch with our granular contract does not
make the address invalid. Do not blanket-map a composite to `road`, use keyword
replacement to repair it, or discard it as non-address text. Adjudicate its spans
before full supervision; leave genuinely ambiguous rows unresolved. Earlier audit
references to “label defects” mean mapping incompatibilities, not invalid premises.

## Locality and administrative fields

- `city` is the primary municipality/town/locality used as the address city.
- `suburb` is a named neighborhood or subdivision within a city.
- `city_district` is an explicitly named borough/district of a city.
- `state_district` is a county/province-level subdivision below `state`.
- Do not convert suburb/district labels based on intuition. If the text gives
  no reliable cue between two labels, flag the whole record for adjudication and
  exclude it from fully supervised data until resolved; record source type evidence
  only in metadata. Do not accept the unresolved span as `O`.
- Do not label country, region, or locality fields absent from the input,
  even when the source record contains them.

## Country-specific interpretation decisions

- Romanized Japanese compound property locators can be `house_number`, including
  chome–block–building digits compressed into one hyphenated sequence. The
  [UPU/Japan Post examples](https://www.upu.int/UPU/media/upu/PostalEntitiesFiles/addressingUnit/jpnEn.pdf)
  distinguish this numbering from street numbering. Do not invent a road. When
  chome is explicitly attached to a named neighborhood, retain that whole named
  span as `suburb` without duplicating its digit. Explicit `1F` is `level`;
  a separately written apartment number can be `unit` when context and reviewed
  source structure establish that role. An unexplained surplus number remains
  uncertain. Keep `-shi` with `city`, `-ken` with `state`, and an established
  ward within a city as `city_district`; do not fabricate absent suffixes.
- Philippine administrative regions above provinces use `country_region`, with
  the province as `state` in this schema. For example, Mimaropa and Oriental
  Mindoro have those [region/province roles in PSA's classification](https://psa.gov.ph/classification/psgc/provinces/1700000000).
  Preserve historical spelling and only the names actually supplied.
- US rural-route delivery uses `RR 1 BOX 13`, distinct from a post-office-box
  address in [USPS Publication 28](https://pe.usps.com/text/pub28/pub28c2_021.htm).
  Our schema convention is `road: RR 1`, `house_number: BOX 13`: the latter
  identifies the delivery point on that route, not a civic building number.
  Preserve spelling/case and the box prefix; do not invent a street or relabel
  every bare `box` as `po_box`. Explicit `PO Box` remains `po_box`. This resolves
  the reviewed rural-route examples, not unrelated ambiguous box references.
- Australian G-NAF `locality_name` is rendered as `city`, the primary postal
  locality in this contract, not an inferred parent municipality. Australia Post
  places the [locality/suburb alongside state and postcode](https://auspost.com.au/personal/sending/sending-guidelines/addressing-guidelines).
  Keep the source locality even when its geographic role is a suburb; do not
  silently omit it to avoid this mapping decision. G-NAF address-detail IDs group
  premises; street-locality IDs are separate street groups, not entity IDs.
  When no civic number exists, render an attested lot locator as `house_number`
  with `LOT` and the source prefix/number/suffix. [Australia Post's addressing
  standard describes this fallback](https://auspost.com.au/content/dam/auspost_corp/media/documents/australia-post-addressing-standards-1999.pdf).
  If both exist, the civic-address rendering uses the civic number and records
  the omitted lot alternative in metadata. Missing road or postcode does not
  invalidate a partial/premise-led input; never invent either.
  Preserve letter-only unit/floor designators even when the numeric subfield is
  empty (`UNIT A`, `LEVEL B`). G-NAF [defines secondary address information to
  include prefixes and suffixes](https://docs.geoscape.com.au/projects/gnaf_desc/en/stable/overview.html).
  A range-end suffix without its numeric endpoint is quarantined pending review;
  do not invent the missing endpoint from the first number.
- Indian taluk/tehsil names with supporting administrative context map to
  `state_district`, our non-city administrative-subdivision field below `state`.
  This does not assert that all such subdivisions are at the same administrative
  depth. [Bengaluru Urban's official description identifies Bengaluru North,
  South and East as taluks](https://bengaluruurban.nic.in/en/aboutdistrict/).
  When those attested names occur as separate subdivisions alongside Bengaluru
  in the reviewed source, retain that role; do not blanket-map arbitrary directional
  neighbourhood descriptions or rewrite names to current administrative boundaries.
- In Vietnamese city context, explicitly designated `Phường` (or unambiguous
  `P`/`P.` ward shorthand) is `suburb`; explicit urban `Quận` is `city_district`.
  Keep the designation inside the span. This maps wards and districts to our
  existing granularity; it is not a translation equating wards with suburbs.
  [Vietnam's government describes wards as commune-level units](https://en.baochinhphu.vn/names-and-administrative-centers-of-34-provinces-and-centrally-run-cities-specified-111250415094350491.htm).
  Do not blanket-convert the source's `District` tag, which can cover multiple
  roles. Preserve historical names and hierarchies rather than rewriting them to
  match administrative reorganizations.
- A kilometre marker locating premises along a road can be `house_number`, including
  its prefix: `Km 9`, not just `9`. This is a property-locator convention in our
  schema, not a claim of civic numbering. [Hanoi University's published address](https://strive.hanu.edu.vn/about-university/)
  separates `Km 9` from `Nguyen Trai Street`. Context must distinguish a premises
  address from a distance or travel direction; never globally relabel all distances.
- `Dublin 2` / `Dublin 4`, when used as the primary postal locality, stay together
  as `city`; a separately present Eircode is `postcode`. This is our extraction
  convention, not a claim about municipal boundaries. [An Post requires the postal
  district and distinguishes postal addresses from geographic location](https://www.anpost.com/Post-Parcels/Sending/Correct-Address).
  Do not turn a bare district number into an invented Eircode.
- A named institutional campus can be `house` when context establishes a premises
  role. Departmental recipients without a premises role remain `O`. An intra-city
  postal locality can be `suburb` when source context supports that role, even if
  the name is also used for an administrative area; do not import that alternative
  hierarchy without contextual evidence.

## Landmark relations

Use existing `near` for explicit locative relation phrases such as `Near`, `Opposite`,
`Next To`, `Behind` or `Off` when they relate the address to another location. This
is our extraction convention, not a new label or a claim that all these relations
mean the same thing. Preserve the relation's exact text. Label the named target by
its supported role (`house` for a venue/building, `road` for a road, `suburb` for a
neighbourhood); do not treat a landmark as the delivery premise or infer its address.
Ordered repeated spans preserve the relation and target rather than collapsing them
into a single house/road value. Quarantine uncertain target types. Ordinary separators
remain outside spans; unrelated contact headings such as `Phone:` remain `O`.

## Non-address and partial input

- Partial but address-like input is valid: annotate only components present.
- A fragment with no address signal (business description, URL, phone number,
  or free prose) is `rejected` and has no components.
- Retain mixed text verbatim; annotate address spans and leave unrelated text
  as `O`. Do not rewrite, translate, expand, or normalize reviewed text.

## Review and adjudication

Each row receives an annotation and a second-review pass. AI passes are not
independent human raters; agreement is not an inter-annotator reliability estimate. Any
disagreement, uncertain boundary, or locality type is `needs-adjudication`.
The adjudicator records the final decision and a short reason. Only
`accepted` and `rejected` rows with no open issues enter the locked set.

AI curation is authorized for this campaign. Record these labels as `ai-reviewed`,
never `human-reviewed`. Annotate before inspecting model predictions, retain uncertain
rows as `needs-adjudication`, and split by source domain before model selection.
These sets measure agreement with AI judgment; they do not establish human accuracy.

## Required row metadata

Record stable `id`; source URL/domain; original input
text; nullable country/language hints as provided; reviewer;
`annotation_status`; `review_reason` when applicable;
`label_provenance` (`human-reviewed` or `ai-reviewed`); `offset_basis` (`unicode-code-point`);
and components (`label`, `start`, `end`, `raw`). Keep source fields and
evaluation membership separate from the annotation itself.

The initial September 15 AI campaign has 204 accepted and 50 uncertain rows.
Its coarse `complete` flag means a street/property plus city is present (8 accepted
rows), not that a fully specified postal address is present. The other 196 accepted
rows are partial. Do not use this flag as a claim of representative complete-address
coverage. Review timestamps were not recorded per row; do not invent them retroactively.
