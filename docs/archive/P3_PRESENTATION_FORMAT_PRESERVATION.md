# Presentation Replacement Formatting

P3-085 changes `presentation-replace` to edit the matched WPS character range
instead of assigning an entire text frame. The replacement inherits the first
matched character's bold, italic, underline, font name, font size and RGB color;
formatting outside the match remains untouched. This rule is consistent for
regular/grouped text shapes and table-cell text ranges.

An opt-in WPS test creates a text frame with normal, bold and italic runs,
replaces the bold middle run, then checks the saved OOXML run properties and
full logical text. It confirms the prefix remains normal, replacement text
remains bold, and the suffix remains italic. Mixed-format matches use the
first matched character's style for the inserted text.
