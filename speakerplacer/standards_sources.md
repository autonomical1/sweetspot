# Home-theater placement guidance provenance

The angle table in `standards.yaml` is guidance for planning and is marked
`verify`; it is not a compliance certification. The named-channel values are
provisional where the project has not confirmed the exact format document,
revision, and installation context.

| Guidance | Source | Status in this project | Notes |
|---|---|---|---|
| 5.1 L/C/R and LS/RS horizontal placement | [ITU-R BS.775-3, multichannel stereophonic systems](https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.775-3-201208-S%21%21PDF-E.pdf) | Cited as source; exact encoded bounds remain verify | The project applies signed azimuth windows for its optimizer. |
| 7.1.4 overhead channel arrangement | [Dolby 7.1.4 overhead speaker setup guide](https://www.dolby.com/siteassets/about/support/guide/setup-guides/7.1.4-overhead-speaker-placement/7_1_4_overhead_speaker_setup.pdf) | Cited as source; project angle windows remain verify | The source covers overhead placement; it does not establish every custom channel bound. |
| 7.1 rear surrounds, wides, 9.1.6 additions, THX/custom aliases, and unverified elevation bounds | Project defaults in `standards.yaml` | Provisional | Confirm against the applicable format and room before installation. |
| Coincidence threshold, RT60 target, typical material coefficients | Project modeling choices | Derived/provisional | The coincidence rule is max(1 Hz, 2%); absorption values are typical estimates, not product data. |

Room-mode frequencies use the rectangular-room eigenfrequency formula with
`c = 343 m/s`. The report exposes the modal indices and coincidence rule so
these model-derived values can be checked independently. It also shows a
20–250 Hz third-octave Bonello-style mode-count screen; this is a provisional
screening summary, not a room-acceptance certification. Bolt-area classification
is not calculated.
