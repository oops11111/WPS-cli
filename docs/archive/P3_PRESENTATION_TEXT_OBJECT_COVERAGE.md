# Presentation Text Object Snapshot Coverage

P3-083 extends presentation snapshots with text-bearing table detection.
Existing text shapes inside grouped shapes remain separate objects and retain
their XML document order. Each table is one text object whose cells are joined
with tabs and rows with newlines; text runs inside a cell are concatenated once.
Snapshot objects now include `object_type` (`shape` or `table`) along with the
existing index, length, emptiness, placeholder and preview fields.

The parser does not create text objects for pictures, charts, or empty
containers. A fixture with two grouped shapes, a multi-cell table and a
following shape verifies ordering and ensures cell text is not duplicated.
Presentation replacement behavior is unchanged; extending mutations to table
cells or grouped-shape traversal requires its own WPS mutation contract.
