# 7K7 — Cinematic AI Artist Portfolio

A clean, cinematic single-page website for a cinematic AI artist's curriculum vitae and portfolio, hosted on AWS S3 + CloudFront.

## Features

- **Dark cinematic theme** — near-black background, gold accents, film-grain overlay
- **Sections** — Hero, About, Skills, Portfolio grid, CV / Experience timeline, Contact form
- **Typography** — Cormorant Garamond (headings) + Inter (body) + Space Mono (labels/code)
- **Scroll animations** — IntersectionObserver reveal, respects `prefers-reduced-motion`
- **Fully responsive** — mobile hamburger nav, fluid grid, accessible markup
- **Static** — no build step, pure HTML / CSS / JS

## Hosting

The site is hosted on **AWS S3 + CloudFront** at `https://7k7.synthesis.run`.

Automated deploys run via GitHub Actions: every push to `main` runs `cdk deploy` and syncs static assets to S3, then invalidates the CloudFront cache.

### Infrastructure (CDK)

The CDK stacks live in the `infra/` directory:

| Stack | Purpose |
|---|---|
| `SevenK7GitHubOidc` | OIDC identity provider + IAM roles for GitHub Actions |
| `SevenK7StaticSite` | S3 bucket, CloudFront distribution, ACM certificate, optional Route 53 record |

#### CDK parameters (infra/config.toml)

| Key | Required | Description |
|---|---|---|
| `domain_name` | Yes (default: `7k7.synthesis.run`) | Custom domain for the site |
| `hosted_zone_id` | No | Route 53 hosted-zone ID — enables automatic cert creation and DNS alias record |
| `hosted_zone_name` | No (default: `domain_name`) | Route 53 zone name; set to apex/parent zone when domain is a subdomain (e.g. `synthesis.run`) |

Store these values in `infra/config.toml` under the `[cdk]` table.
Command-line `cdk deploy -c key=value` still works and overrides file values.

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
infra/                  # AWS CDK infrastructure (Python)
infra/config.toml       # Deployment parameters loaded by app.py
.github/workflows/      # GitHub Actions (deploy on push to main, diff on PR)
```
