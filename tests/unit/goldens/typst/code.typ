#set document(title: "code")
#set page(paper: "a4", margin: 2cm)
#set text(font: "Libertinus Serif", size: 11pt)

#align(center)[#text(20pt, weight: "bold")[code]]

Run `n2f build --target docs` then check `page.pdf`.

```python
def area(w, h):
    return w * h  # mm²
```

```
plain fence
```

```
indented code block
```

Inline with a backtick: #raw("a`b").

#text(size: 8pt, style: "italic")[This design was produced with an AI system and has not been reviewed by a licensed engineer.]
