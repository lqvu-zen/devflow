# Generated-look tells (registry, dated 2026-10-29)

A tell is a device that makes a screen read as generated. Most began as good ideas; they became tells by being produced by default, without a reason. This registry merges taste-skill (vendored `c924fad`), Impeccable `5e745ac` (Apache-2.0, `craft-floor.md` § Refuse), Hallmark `8f6969f` (MIT, `gates.md`), Open Design `5e9a5e6` (Apache-2.0, `craft/anti-ai-slop.md`) and the frontend-design skill. Rules are restated in devflow's words (D1). It names no replacement font, colour or component: the fix is a procedure.

The format follows Hallmark's.

| Column | Values |
|---|---|
| Tier | **floor** (no admired design breaks it on purpose), **reflex** (a default a generator falls into; a stated reason waives it), **finish** (craft detail, reported, never blocking) |
| Class | **measurable** (a number or a selector decides it), **rule-of-thumb**, **judgement** |
| Taste | every row is a taste rule unless its class is measurable; taste rows rank below the project's rules (SKILL.md precedence) |
| Flag | **marketing** marks a row the inspector's app-screen mode would skip: it does not apply to an app or game screen |
| Waiver | a tell is waived when the design system or the project's `allow` map names the thing (mono labels, arrows, eyebrows, serif display) |

## Colour and surface

| Tell | Tier | Class | Flag | Fix | Source |
|---|---|---|---|---|---|
| Violet or indigo gradients on the hero, buttons or glows; a two-stop purple→blue, blue→cyan or indigo→pink hero | floor | measurable | marketing | the design system's palette; flat colour | TS, HM 2a, OD 2 |
| The framework's default accent as the solid accent (Tailwind indigo/violet: `#6366f1`, `#4f46e5`, `#4338ca`, `#3730a3`, `#8b5cf6`, `#7c3aed`, `#a855f7`) | floor | measurable | | the design system's `primary` | OD 1, HM 74 |
| Gradient-filled text | floor | measurable | | solid ink; weight or size for emphasis | TS, HM 2, IMP |
| Glass panels and decorative blur: backdrop blur, translucent cards, blurred orbs, aurora washes | reflex | judgement | | opaque surfaces one tone step from the ground | TS, HM 29, IMP |
| A glowing or gradient "Get started" button | floor | measurable | marketing | a flat button named for its action | TS |
| A soft grey drop shadow under every card; a hard offset shadow (`4px 4px 0`) outside a neobrutalist design | reflex | measurable | | a tone step, or no box; shadows with offset and blur | TS, IMP |
| Near-black ground with one neon accent and a glow | reflex | judgement | | the design system's dark palette, no glow | TS |
| Yellow-cream ground with a high-contrast serif display and a terracotta accent | reflex | judgement | | move one axis: the accent first, then the ground, then the display | TS, HM 65, FD |
| Broadsheet look: hairline rules everywhere, zero radius, dense columns | reflex | judgement | marketing | structure from space and tone | TS, FD |
| Pure `#000` or `#fff`, or zero-chroma neutrals, outside the token block | reflex | measurable | | tint toward the design system's hue | HM 7, 22 |
| The accent used 6 or more times in a rendered body | reflex | rule-of-thumb | | cap at about 2 visible uses per screen | OD |
| Light or dark picked by category rather than by use scene | reflex | judgement | | pick from who uses it, where, under what light | IMP |

## Type

| Tell | Tier | Class | Flag | Fix | Source |
|---|---|---|---|---|---|
| The same default typeface on every generated page; a system face as the display voice | reflex | judgement | | the design system's type roles | TS, HM 1, IMP |
| Nine or more nearly equal font sizes | reflex | measurable | | about five roles, far apart (D7); the inspector flags over 9 on web and over 10 in app mode | TS |
| Headline as a full sentence at display size over two lines | floor | measurable | marketing | a title of about five words | TS |
| Mono as costume: monospace on labels, captions or meta rows when the content is not code, data or measurement | reflex | judgement | | the text face; tabular figures for data | TS, IMP, HM 64 |
| Eyebrow: a tiny tracked uppercase label above a heading. Keep it only when it carries information the heading does not, and say which | reflex | judgement | | fold it into the heading, or delete | TS, FD, IMP, HM 54 |
| Tracked caps: any label, caption, tag or nav link at 15 px or under set uppercase or letter-spaced past 0.03 em | reflex | measurable | | the body face, a step smaller, sentence case | HM 67 |
| One word of a headline in italic serif, colour or underline | reflex | judgement | marketing | one face, one colour | TS, HM 38 |
| An oversized italic or high-contrast serif as the shortcut to "premium" | reflex | judgement | marketing | the design system's type | TS, FD |
| Running text outside 45–75 characters per line | reflex | measurable | | `max-width` of about 65ch | HM 25, IMP |

## Structure and layout

| Tell | Tier | Class | Flag | Fix | Source |
|---|---|---|---|---|---|
| Three identical feature cards, each with an icon in a rounded square; a card inside a card | reflex | judgement | marketing | vary widths and heights; one containment layer | TS, HM 3/4, IMP |
| A rounded card with a coloured left-border accent over 1 px | reflex | measurable | | drop either the radius or the border | OD 5, IMP |
| The hero-metric template: a big number, a small label, supporting stats, an accent | reflex | judgement | marketing | pair the figure with what it means | IMP, HM 46b |
| Every section the same layout family, or the same gap, or the same fade-up | reflex | judgement | marketing | a different composition per section | TS, HM 8/9 |
| Stock section order: hero, logos, features, testimonial, pricing, CTA | reflex | judgement | marketing | the order of the argument | TS, OD, HM 8 |
| Everything centred (over about 72%) | reflex | measurable | marketing | left-anchored with one centred moment | TS |
| One medium border radius on everything | reflex | judgement | | square or fully round, chosen once | TS |
| Fake dashboard or product mock built from grey bars and donut charts | reflex | judgement | marketing | a real interface fragment, or no image | TS, HM 84 |
| A modal for a task that needs neither interruption nor protected focus | reflex | judgement | | inline | IMP |
| Decorative blob or wave SVG backgrounds | finish | judgement | marketing | remove | OD |
| Index numbering (01 / 02 / 03, "Step 02") that carries no sequence | reflex | judgement | marketing | order by position or by the words | TS, IMP |
| Thin rules, ruled grids and outlined boxes as the only structure | reflex | judgement | | space, tone steps, filled shapes | TS |
| Design-tool chrome as ornament: crosshairs, crop marks, selection handles, dashed guides | reflex | judgement | marketing | remove | TS |
| Over about 12 raw hex values outside `:root` | reflex | measurable | | the tokens | OD |
| More than about 80 words in a 900 px window | not imported | | | a word-count gate is taste (D7) | HM 58 |

## Assets and icons

| Tell | Tier | Class | Flag | Fix | Source |
|---|---|---|---|---|---|
| Emoji or text symbols (♪, ✓, →, ★) standing in for icons or bullets | floor | measurable | | the icon set, or a word | TS `emoji`, UP no-emoji-icons, OD 3, IMP, HM 30a |
| Two icon libraries or stroke weights on one screen | reflex | measurable | | one set, one weight | HM 30b |
| External placeholder image CDNs (`unsplash.com`, `placehold.co`, `picsum.photos`) | reflex | measurable | | the project's own assets | OD |
| A grey box or CSS block where a picture belongs | floor | judgement | | a real picture, or a design that needs none | TS |
| Geometric masks (circle, polygon, radial cutout) approximating a photographic subject's edge | reflex | judgement | marketing | a real cut-out, or omit | IMP |

## Copy

| Tell | Tier | Class | Flag | Fix | Source |
|---|---|---|---|---|---|
| Filler and genre words: unlock, supercharge, seamless, elevate, effortless, cutting-edge, all-in-one; "not just X, it's Y"; tricolon headlines; "Get started" and "Learn more" as labels | floor | rule-of-thumb | | say what the product does in its own nouns | TS, HM 19 |
| Lorem ipsum, "feature one / two / three", placeholder names | floor | measurable | | known placeholder content is not a finding; report only how the layout copes (SKILL.md) | OD 7, HM 19 |
| Invented metrics, testimonials, logo walls ("10× faster", "99.9% uptime") | floor | judgement | marketing | the real number, or a labelled placeholder | OD 6, HM 46a |
| Template punctuation: meta strings joined with middle dots, an arrow glued to link text, decorative status dots | reflex | judgement | | line breaks, columns; a verb as the label | FD, HM 63 |
| Performative labels ("Field notes", "Quietly trusted by") | reflex | rule-of-thumb | marketing | plain section names | TS |
| A form that prints success with no request behind it | floor | judgement | | no success state until the form is wired | HM 70 |

## Motion

| Tell | Tier | Class | Flag | Fix | Source |
|---|---|---|---|---|---|
| Identical fade-up on every block; a dozen staggered hero entrances | reflex | judgement | marketing | one signature move | TS, FD, IMP |
| The same hover lift or scale on every card; hover on a non-interactive element | reflex | judgement | | one signal per element, on the container | TS, HM 11 |
| Bounce or overshoot easing on UI state; infinite loops that mean nothing | reflex | judgement | | exponential ease-out | TS, HM 12 |
| `transition: all`; animating layout properties | floor | measurable | | list the properties; `transform` and `opacity` | HM 10a, GSAP |
| No reduced-motion fallback on a keyframe or transform transition | floor | measurable | | add it | HM 27, W 2.3.3 |
| Content hidden at rest that depends on JavaScript to show | floor | measurable | | visible by default | HM 62 |

## Why removal is not enough

A screen with every tell removed and nothing put in their place is an empty screen with good manners, and that is a tell too. The tells were filling a gap where an idea should have been: take the direction from the design system first, spend boldness in one place, then run the registry.
