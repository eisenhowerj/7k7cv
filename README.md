# 7K7 — Cinematic AI Artist Portfolio

A clean, cinematic single-page GitHub Pages website for a cinematic AI artist's curriculum vitae and portfolio.

## Features

- **Dark cinematic theme** — near-black background, gold accents, film-grain overlay
- **Sections** — Hero, About, Skills, Portfolio grid, CV / Experience timeline, Contact form
- **Typography** — Cormorant Garamond (headings) + Inter (body) + Space Mono (labels/code)
- **Scroll animations** — IntersectionObserver reveal, respects `prefers-reduced-motion`
- **Fully responsive** — mobile hamburger nav, fluid grid, accessible markup
- **Static** — no build step, pure HTML / CSS / JS, works on GitHub Pages out of the box

## Enabling GitHub Pages

1. Merge this PR into `main`
2. Go to **Settings → Pages** in this repository
3. Under **Source**, select **Deploy from a branch**
4. Choose `main` branch, folder `/` (root), then click **Save**
5. Your site will be live at `https://eisenhowerj.github.io/7k7cv/` within a minute

## Replacing the logo

The current logo file is `assets/logo.svg` (an SVG recreation of the 7K7 ibex mark).  
To swap in your final logo:

1. Add your logo file to the `assets/` folder (e.g. `assets/logo.png` or `assets/logo.svg`)
2. Update the two `<img src="assets/logo.svg" …>` references in `index.html` (navbar and hero)
3. Adjust `width` / `height` attributes if the aspect ratio differs from the current square

## Contact form

The contact form uses [Formspree](https://formspree.io) as a backend.  
To activate it:

1. Create a free account at formspree.io
2. Create a new form and copy your endpoint ID
3. In `index.html`, replace `YOUR_FORM_ID` in the `<form action="…">` attribute with your ID

## File structure

```
index.html              # Main single-page site
css/style.css           # All styles
js/main.js              # Interactions (nav, scroll reveal, smooth scroll)
assets/logo.svg         # 7K7 ibex logo mark (replace with final asset)
assets/logo-placeholder.svg  # Original placeholder (can be deleted)
.nojekyll               # Tells GitHub Pages to skip Jekyll processing
```
