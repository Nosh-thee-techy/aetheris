# Label log for 4–6 May 2024

`backtest/labels.csv` has seven flooded places. There are no `not_flooded` rows. A place these reports do not name is absent, and the scorer treats that as unknown.

The event window is 4 May through 6 May 2024. The Nation reports that River Nyando burst its banks at 16:00 on Saturday 4 May. The report radar scene is the Sentinel-1A pass on 6 May.

Each label is a place a report named, at the scale of that sentence:

- Ahero is the township.
- Kabonyo Kanyagwal and Kakola Ombaka are the areas named with household counts.
- Nyamasao is the dispensary the same Nation report says was overtaken.
- Ombeyi is the location. Seven villages were submerged and not named, so they are not seven zones.
- Kobura is the village The Star names, not the whole ward.
- Kadibo is the sub-county. The Star counts evacuated and marooned people and names no village.

Roads reported impassable in Muhoroni and Nyakach are not flood labels. Onjiko Secondary School and Bunde Dispensary appear as a rescue centre and a medical camp, so they are not labeled flooded. A warning to people living near River Miriu is not a report that those villages flooded.

Kenya News Agency says lake backflow made the Ahero flooding worse. That is the lake mode the rainfall rule does not see, sitting inside an otherwise riverine label.

These are news reports. They favour places rescuers and reporters could reach, and they do not draw a flood edge. Household counts are the source's figures, not a surveyed extent.

The scored result for these seven rows is `docs/agreement.md`.
