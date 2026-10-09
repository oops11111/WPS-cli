# Presentation Nested Text Replacement

P3-084 extends WPS-backed `presentation-replace` to recurse through grouped
shapes and visit table cells individually. Shapes and cells are processed once;
the expected match count is still preflighted from the saved package. After
WPS saves, the operation requires both an exact backend replacement-count
match and exact logical text equality for every slide, including slides
outside a slide-scoped request. Failed validation returns
`VALIDATION_FAILED`; the pre-write backup remains available for recovery.

An opt-in local WPS integration created a temporary deck with two grouped text
shapes and a 2x2 table. All four `needle` matches were replaced, the unchanged
cell remained unchanged, and the saved deck's per-slide text exactly matched
the expected output. No remote Git or cloud upload is required.

Text range replacement still assigns the updated range as a whole. Character
format preservation across mixed runs is not guaranteed; P3-085 will define
and test that behavior before changing the replacement strategy.
