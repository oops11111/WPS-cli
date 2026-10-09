# Presentation Object-Level Read-Back

P3-086 scopes presentation replacement matches to individual paragraphs in
text shapes and table cells. Counts cannot be formed by concatenating the end
of one shape/cell with the start of another. After WPS saves, read-back compares
the ordered slide index, object index, object type and paragraph/cell text
segments against the exact expected result. A matching aggregate character
count is not sufficient for success.

Offline fixtures verify that cross-shape and cross-cell boundary strings do
not count as matches. WPS grouped-shape/table replacement and mixed-run format
tests confirm that actual supported mutations satisfy the object-level
contract.
