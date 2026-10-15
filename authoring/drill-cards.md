# Need-to-know cards for Practice drills

Practice mode (`practice.html`) turns every lab milestone into a **drill**: the learner is shown one function to write, with the rest of the lab's solution already in the file, and a checker that says ✔ or ✘. The learner has **not read the chapter**. A card is the smallest amount of theory that lets them attempt the function anyway. It appears above the task; the lab page's full explanation and the chapter are one click away for afterwards.

## The file

`<course>/labs/code/labNN/drills/mN.html`, one per milestone N, an HTML **fragment** (no doctype, head or body). `python3 authoring/build_drills.py` folds it into `drills/lab.json`; do not run that script yourself, the coordinator does. The milestones, their titles and the functions each one asks for are in `drills/lab.json` (`milestones[].title`, `.write`); the stubbed file the learner sees is `drills/mN.py`.

## What a card says

100 to 200 words, in this order:

1. **The one idea** (one or two sentences): the mechanism the function implements, in plain words. Why it exists, not its history.
2. **The shape of the answer** (two to five sentences or a short list): what goes in, what comes out, the one or two rules that matter (an invariant, an edge case the checker tests, the order of operations). Name the function(s) and the helper(s) already in the file that it should use. Read the stub's docstring in `drills/mN.py` first: do not repeat it, build on it.
3. **One concrete example** with small numbers, as a sentence or a two-line `<pre><code>` block.
4. **Read more**, one line: a link to the chapter section that teaches it. Take the page path from `authoring/link-index.md`. Cards are rendered on `practice.html` at the site root, so write links from the root, `<course>/chapters/<file>#<section-id>`, never with `../`. Section ids are the heading text lowercased with non-letters turned into hyphens (check the chapter's `<h2>` text).

Optional, only when it saves words: one small inline SVG (`<figure class="diagram">`, width 760, site classes, marker ids `ah<COURSE><LAB>m<N>a`, see `authoring/guide.md` section 6) or an inline equation (`<span class="tex" data-tex="…">fallback</span>`).

## What a card does not do

- It does not restate the task or the checkpoint; the drill page shows both from the lab page.
- It does not give the solution or the hints; those are there too, behind a click.
- It does not say "in this chapter" or "as we saw": the reader has read nothing.
- No em-dashes, British spelling (except "artifact"), no names in the first sentence, every term defined in the sentence that uses it. Plain, short sentences.

## Example (A0 Lab 6, milestone 2, `pack` and `score`)

```html
<p>A packing heuristic is a tiny function that looks at one item and one open bin and returns a number: the higher, the more it wants that bin. Online bin packing then takes items one at a time, asks the heuristic about every bin with room, and puts the item in the bin with the highest answer, or opens a new bin if none fit.</p>
<p><code>pack(items, priority)</code> runs that loop and returns the number of bins used. <code>score(src, instances)</code> compiles a candidate with <code>make_heuristic</code> (already written) and packs every instance; its result must always be a number, so anything that goes wrong (an exception, a non-number, running out of fuel) scores <code>PENALTY</code> instead of raising. The checker counts how often <code>priority</code> is called: once per feasible bin, in bin order.</p>
<pre><code>items 20, 30, 60, 20, 50 into bins of 100
first fit:  [20 30] [60 20] [50]      -> 3 bins
best fit:   [20 30 50] [60 20]        -> 2 bins</code></pre>
<p>Read more: <a href="ml-foundations/chapters/22-running-candidates.html#every-outcome-is-a-number">A0 chapter 22, every outcome is a number</a>.</p>
```
