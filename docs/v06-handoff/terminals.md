# Published terminal numbering (read from the diagrams themselves, not inferred)

All four facts were read by rendering the maker's PDF pages to images and viewing the drawings.
Local copies: docs/v06-handoff/dl/

## 1 and 2. Omron E5CC-QX2ASM-800 and E5CC-RX2ASM-800 (screw-terminal E5CC-800)
Source: Omron datasheet "Digital Temperature Controller (Simple Type) E5CC-800/E5CC-B-800/E5CC-U-800 (48 x 48 mm)", p.10 "External Connections", section "E5CC-800 (Screw Terminal Blocks)". No revision or date is printed in this copy. It cites User's Manual H174; I did not obtain H174.
URLs: https://baa.vn/document/e5cc-800-series-omron-bo-dieu-khien-nhiet-do-267-datasheet.pdf and https://cdn.eicom.ru/media/PDF/1031350.pdf (the latter is the combined E5CC/E5EC/E5AC catalogue, same E5CC-800 page).
Confidence for every row below: Omron's own document, via a third-party host (the Omron sites refused fetching, 403).

| Function | Terminals | Note from the diagram |
|---|---|---|
| Power supply, 100 to 240 VAC | 11, 12 | Drawn with a "~" source symbol; no L/N labels. "(no polarity)" is printed under the 24 VAC/VDC box only, so the datasheet does not say L/N is free for the AC version. |
| Control output 1, voltage (SSR), model QX | 1 (+), 2 (-) | Labelled "OUT1 Q"; "Voltage output (for driving SSR) 12 VDC, 21 mA". Terminal 3 is grey = do not wire. |
| Control output 1, relay, model RX | 1 and 2 | Labelled "OUT1 R", a relay contact between 1 and 2. Terminal 3 is grey = do not wire. |
| Auxiliary output 1 | 9, 10 | Bracket labelled "Auxiliary output 1" |
| Auxiliary output 2 | 7, 8 | Bracket labelled "Auxiliary output 2" |
| Thermocouple input (TC) | 6 (+), 5 (-) | Terminal 4 is grey = do not wire. |

Quote (diagram labels): "(3) Input Power Supply 100 to 240 VAC ... 11 12"; "Auxiliary output 2" beside 7-8.

### Relay rating (E5CC-RX2ASM-800, control output 1)
- Datasheet specifications: "SPST-NO, 250 VAC, 3 A (resistive load)", electrical life 100,000 operations, minimum applicable load 5 V, 10 mA (reference value). Same page 10 and the specification table.
- Auxiliary outputs (both models): SPST-NO relays, 250 VAC, 3 A (resistive load) for the E5CC-800; 100,000 operations; minimum load 10 mA at 5 V.
- The electrical life curve (p.9) is for "250 VAC, 30 VDC (resistive load) cos phi = 1" only.
- Inductive, AC-15 or cos phi = 0.4 rating: NOT FOUND in the datasheet. Looked in: the H179-type datasheet text and curve page (both copies). Not looked in: H174 user's manual (not obtained). Treat any inductive load as unrated.

## 3. Omron D4N-1120
Source: Omron "D4N Miniature Safety Limit Switch", catalogue pages G-219 to G-228 (Safety Sensors / Components), file c130_d4n_miniature_safety_limit_switch_datasheet_en.pdf. No revision or date is shown in this copy.
URL: https://files.omron.eu/downloads/latest/datasheet/en/c130_d4n_miniature_safety_limit_switch_datasheet_en.pdf?v=1 (the maker's own host, downloaded).
Confidence: read in the maker's own document.
- Model identity (p. G-220): D4N-1120 = roller lever (resin lever, resin roller), 1-conduit Pg13.5, 1NC/1NO snap-action, direct opening. Legend: "1: 1NC/1NO (snap-action)".
- Terminals (p. G-227, "Contact Form", row D4N-x1x, 1NC/1NO snap-action): NO = 13-14, NC = 31-32. There is NO 11-12 and NO 23-24 on this model.
- Quote: "Only NC contacts 31-32 have an approved direct opening mechanism."
- Quote: "The terminals 13-14 and 31-32 can be used as unlike poles."
- Note on the same page: terminals numbered per EN50013, contact forms per IEC947-5-1.
- AC-15 rating (p. G-224 and the specifications table): utilization category AC-15, rated operating current Ie 3 A, rated operating voltage Ue 240 V; DC-13: 0.27 A at 250 V. The UL/CSA table (same page) lists 240 VAC make 30 A, break 3 A; 120 VAC make 60 A, break 6 A; carry current 10 A.
- Electrical life: 500,000 operations min. for resistive 3 A at 250 VAC.
- Other D4N-x2x/xAx variants use 11-12 with 31-32 or 33-34, so those numbers must not be copied across.

## 4. Crydom (Sensata) D2425
Source: Crydom "Series 1, 10-90 Amp, 120/240 Vac - AC OUTPUT" datasheet, FastFax Document No. 151, "SERIES1 Rev. 102104", (c) 2003 Crydom Corp. The model table lists D2425 (25 A, DC control 3-32 Vdc). Copy distributed by Jameco, hosted on Octopart (file is titled for the A2450 but covers the whole Series 1 incl. D2425).
URL: https://datasheet.octopart.com/A2450-Crydom-datasheet-47693268.pdf (page 2 of 3, dimensions drawing).
Confidence: maker's document via a third-party host. It is an old revision (2003); I could not fetch the current Sensata/Crydom sheet (sensata.com, Mouser, element14, RS, TME, alldatasheet all returned 403).
- Load (output) terminals: 1 and 2, drawn as "1 OUTPUT 2" (AC load, no polarity).
- Control (input) terminals: 3 = "+", 4 = "-", drawn as "4 INPUT 3" with a minus sign at 4 and a plus sign at 3.
- Quote (drawing labels): "OUTPUT" between 1 and 2; "INPUT" between 4 and 3.
- Related D-type specs from the same sheet: control range 3-32 Vdc, max reverse voltage -32 Vdc, max turn-on voltage 3.0 Vdc, turn-off 1.0 Vdc, input current 3.4 mA at 5 Vdc and 20 mA at 28 Vdc.
- Suffix note: the drawing is the same for screw and Faston versions. Suffix G changes the control range to 4.5-32 Vdc; D2425D in some listings is a different (dual-output) part and should not be assumed to match.

## Not found / not done
- E5CC-800 User's Manual H174: not obtained, so no cross-check of terminal numbers or any inductive relay rating there.
- Whether an AC supply on 11-12 has any L/N preference: the datasheet gives no marking.
- Current-revision Sensata D2425 sheet: not retrievable; the 2003 revision is the only maker's document read.
