#set document(title: "table")
#set page(paper: "a4", margin: 2cm)
#set text(font: "Libertinus Serif", size: 11pt)

#align(center)[#text(20pt, weight: "bold")[table]]

#table(
  columns: 3,
  align: (left, center, right),
  table.header([*Part*], [*Qty*], [*Unit cost*]),
  [Base], [1], [12.50 USD],
  [Bracket], [2], [_4.00_ USD],
  [M4 x 10 screw], [4], [],
)

#text(size: 8pt, style: "italic")[This design was produced with an AI system and has not been reviewed by a licensed engineer.]
