---
title: "feat: Add Raycast Extension Builder Skill"
type: feat
status: completed
date: 2026-03-26
---

# feat: Add Raycast Extension Builder Skill

## Overview

Create a Claude Code skill that encodes deep knowledge of Raycast extension development -- architecture, manifest structure, API components, CLI workflow, changelog conventions, linting, formatting, publishing requirements, and common patterns. The skill helps developers build, debug, and publish Raycast extensions correctly the first time.

## Problem Statement / Motivation

Building Raycast extensions involves many non-obvious conventions: npm-only (no yarn/pnpm), `{PR_MERGE_DATE}` changelog placeholders, Title Case naming rules, command-to-file mapping, three distinct command modes, ESLint flat config, 512x512 icon requirements, and Store submission checklists. Developers hit these gotchas repeatedly. A skill that encodes this knowledge eliminates the trial-and-error cycle.

## Proposed Solution

Create a standalone skill at `~/.claude/skills/raycast-extension/` with:

1. **`SKILL.md`** -- Main skill file with role definition, core knowledge, and workflow guidance
2. **`references/api-patterns.md`** -- Curated reference of commonly used `@raycast/api` components and `@raycast/utils` hooks
3. **`references/manifest-reference.md`** -- Complete `package.json` manifest field reference including valid categories, preference types, command modes, interval values
4. **`references/store-checklist.md`** -- Publishing requirements and common rejection reasons

### Skill Architecture

The skill follows the **declarative/reference pattern** (like `nano-banana-2`) rather than a procedural workflow. It encodes domain knowledge that Claude applies contextually when helping with Raycast extension development.

## Technical Approach

### File Structure

```
~/.claude/skills/raycast-extension/
├── SKILL.md                          # Main skill definition
└── references/
    ├── api-patterns.md               # Core API components & hooks
    ├── manifest-reference.md         # package.json fields, categories, modes
    └── store-checklist.md            # Publishing requirements
```

### SKILL.md Structure

```yaml
---
name: raycast-extension
description: "Build, debug, and publish Raycast extensions. Use when the user
  wants to create a Raycast extension, add commands, fix build errors, prepare
  for Store submission, or work with the Raycast API. Triggers on 'raycast',
  'raycast extension', 'raycast command', 'raycast api', '@raycast/api',
  'ray build', 'ray develop', or mentions of Raycast development."
metadata:
  version: 1.0.0
---
```

**Body sections:**

#### 1. Role & Context
- "You are an expert Raycast extension developer..."
- Technology stack: TypeScript, React, Node.js, `@raycast/api`, `@raycast/utils`
- npm is the only supported package manager (not yarn, not pnpm)

#### 2. Extension Architecture
- File structure: `src/`, `assets/`, `media/`, manifest in `package.json`
- Command mapping rule: each `commands[].name` maps to `src/<name>.tsx`
- Three command modes: `"view"` (renders UI), `"no-view"` (runs silently), `"menu-bar"` (menu bar icon)
- File extensions: `.tsx`/`.jsx` for view commands, `.ts`/`.js` for no-view

#### 3. Manifest (`package.json`)
- Required fields: `name`, `title`, `description`, `icon`, `author`, `platforms`, `categories`, `license: "MIT"`, `commands`
- Command object: `name`, `title`, `description`, `mode` (required); `interval`, `arguments`, `preferences`, `keywords` (optional)
- Preference scoping: extension-level (shared) vs. command-level (per-command)
- Preference types: `textfield`, `password`, `checkbox`, `dropdown`, `appPicker`, `file`, `directory`
- Valid categories: `Applications`, `Communication`, `Data`, `Documentation`, `Design Tools`, `Developer Tools`, `Finance`, `Fun`, `Media`, `News`, `Productivity`, `Security`, `System`, `Web`, `Other`
- `platforms`: `["macOS"]`, `["Windows"]`, or `["macOS", "Windows"]`
- Background refresh `interval` values: `"10s"`, `"30s"`, `"1m"`, `"10m"`, `"1h"`, `"6h"`, `"12h"`, `"1d"` (minimum `"1m"` for Store)
- Reference: `references/manifest-reference.md`

#### 4. Development Workflow
- Scaffolding: `npx create-raycast-extension@latest` or Raycast's built-in "Create Extension" command
- `npm run dev` -- hot reload development mode
- `npm run build` -- distribution build (stricter than dev; always run before submission)
- `npm run lint` -- ESLint checks
- `npm run lint --fix` -- auto-fix
- `npm run publish` -- creates PR to `raycast/extensions` repo
- Node.js: recommend latest LTS (Node 20.x or 22.x)

#### 5. Code Conventions
- Default export per command file (React component for view, async function for no-view)
- Title Case for extension titles, command titles, action titles (Apple Style Guide)
- Command titles: `<verb> <noun>` pattern ("Search Packages", not "NPM")
- US English spelling required
- No articles in titles ("Search Emoji" not "Search an Emoji")
- Ellipsis for submenu actions ("Set Priority...")

#### 6. Changelog Format
```markdown
## [Change Description] - {PR_MERGE_DATE}
- Change item 1
- Change item 2
```
- `{PR_MERGE_DATE}` is a **literal placeholder string** -- Raycast CI replaces it with the actual date when the PR merges
- Alternative: use `YYYY-MM-DD` for manual dates (private extensions or known merge dates)
- CHANGELOG.md is required for Store publishing

#### 7. Linting & Formatting
- ESLint 9 flat config: `eslint.config.js` with `@raycast/eslint-config`
- Do NOT use `.eslintrc` (old format, will be ignored)
- Custom Raycast rules: `prefer-title-case` (Action titles), `prefer-placeholders` (input fields)
- Prettier: `.prettierrc` ships with scaffolded extensions, use defaults
- Do not add excessive personal ESLint rules -- ecosystem consistency matters

#### 8. Common Patterns
- Reference: `references/api-patterns.md` for full examples
- **List with search**: `List` + `useCachedPromise` + `List.Item` + `List.EmptyView`
- **Detail view**: `Detail` with `markdown` prop + `Detail.Metadata`
- **Forms**: `Form` + `useForm` hook from `@raycast/utils` (handles validation)
- **Grid**: `Grid` with `columns`, `aspectRatio`, `fit` props
- **Navigation**: `useNavigation()` returns `{ push, pop }`
- **Preferences**: `getPreferenceValues<T>()` -- typed access
- **Storage**: `LocalStorage` (persistent) vs `Cache` (fast, may be cleared)
- **Data fetching**: `useFetch` (URL-based), `useCachedPromise` (promise-based with caching), `useExec` (shell commands)
- **Error handling**: `showFailureToast()` from `@raycast/utils` as primary pattern
- **Menu bar**: `MenuBarExtra` component with `MenuBarExtra.Item` and `MenuBarExtra.Submenu`
- **Deeplinks**: `createDeeplink()` for URL-based command entry points
- **Inter-command**: `launchCommand()` for programmatic command launching

#### 9. Critical Warnings
- **OAuth + background commands**: OAuth API methods throw when called from background commands. Always check `environment.launchType` before initiating OAuth in commands with `interval`
- **`isLoading` prop**: Always pass `isLoading` to top-level components (List, Detail, Form, Grid) -- omitting it causes jarring empty state flashes
- **npm only**: `package-lock.json` must be committed. No yarn.lock or pnpm-lock.yaml
- **Default icon = rejection**: Always create a custom 512x512 PNG icon. Use [icon.ray.so](https://icon.ray.so/)
- **No external analytics**: Prohibited in Store extensions
- **No keychain access**: Auto-rejected
- **No separate config commands**: Use the preferences API instead

#### 10. Publishing Checklist
- Reference: `references/store-checklist.md`
- Metadata complete (author, categories, icon, description, license MIT)
- `npm run build` passes
- `npm run lint` passes
- Screenshots: 3-6, 2000x1250 PNG, in `media/` folder
- CHANGELOG.md present with correct format
- README if extension requires setup (API keys, OAuth)
- `package-lock.json` committed
- No sensitive data in screenshots
- Custom icon (not default)

#### 11. Testing
- No official test framework for Raycast extensions
- `npm run dev` for manual testing with hot reload
- Extract business logic into pure functions in `src/utils.ts` -- test with Vitest/Jest
- `npm run build` as type-checking gate (catches errors dev mode misses)
- For AI extensions: use the `evals` system in `package.json`

### references/api-patterns.md Content

Curated code examples for the most common patterns:
- List with search and loading state
- Form with validation (`useForm`)
- Detail with metadata panel
- Grid with custom aspect ratios
- ActionPanel with keyboard shortcuts
- Navigation push/pop
- OAuth flow (with background command guard)
- Preferences access with TypeScript generics
- `useFetch` with pagination
- `useCachedPromise` with revalidation
- `useExec` for shell commands
- `MenuBarExtra` with background refresh
- `LocalStorage` for persistence
- Empty states (`List.EmptyView`, `Grid.EmptyView`)
- Toast notifications (success, failure, animated)
- `launchCommand` for inter-command communication

### references/manifest-reference.md Content

Complete reference for all `package.json` fields:
- Top-level fields with types and requirements
- Command object fields with valid values
- Argument object fields and types (`text`, `password`, `dropdown`)
- Preference object fields and types
- Valid categories (enumerated)
- Valid `interval` values
- `platforms` field options
- Example complete `package.json` for a multi-command extension

### references/store-checklist.md Content

Step-by-step publishing checklist:
- Pre-submission verification steps
- Metadata requirements with examples
- Screenshot specifications and tips
- Common rejection reasons with fixes
- Update workflow (changelog entry, `pull-contributions`, republish)
- Monorepo vs standalone differences (brief note)

## Acceptance Criteria

- [ ] `~/.claude/skills/raycast-extension/SKILL.md` exists with correct frontmatter
- [ ] `~/.claude/skills/raycast-extension/references/api-patterns.md` exists with code examples for all common patterns
- [ ] `~/.claude/skills/raycast-extension/references/manifest-reference.md` exists with complete field reference
- [ ] `~/.claude/skills/raycast-extension/references/store-checklist.md` exists with publishing checklist
- [ ] Skill triggers correctly on "raycast", "raycast extension", "raycast command" etc.
- [ ] Skill provides accurate guidance for creating a new extension from scratch
- [ ] Skill provides accurate guidance for adding commands to existing extensions
- [ ] Skill provides accurate guidance for Store submission preparation
- [ ] Skill covers all three command modes (view, no-view, menu-bar) with correct constraints
- [ ] Skill warns about OAuth + background command incompatibility
- [ ] Skill specifies `{PR_MERGE_DATE}` as a literal placeholder (not a date format)
- [ ] Skill recommends npm only, warns against yarn/pnpm
- [ ] All code examples use TypeScript and follow Raycast naming conventions

## Dependencies & Risks

**Dependencies:**
- None -- this is a standalone skill with no external dependencies

**Risks:**
- **API drift**: Raycast API evolves; references may go stale. Mitigated by linking to official docs for exhaustive coverage and keeping references focused on stable, commonly-used patterns
- **Scope creep**: The Raycast API surface is large. Mitigated by curating the most common patterns rather than attempting exhaustive coverage

## Sources & References

### Internal References
- Existing skill pattern: `~/.claude/skills/nano-banana-2/SKILL.md`
- Skill directory convention: `~/.claude/skills/<name>/SKILL.md` + optional `references/`

### External References
- [Raycast Developer Docs](https://developers.raycast.com/)
- [Best Practices](https://developers.raycast.com/information/best-practices)
- [File Structure](https://developers.raycast.com/information/file-structure)
- [Manifest Reference](https://developers.raycast.com/information/manifest)
- [Prepare for Store](https://developers.raycast.com/basics/prepare-an-extension-for-store)
- [Publish an Extension](https://developers.raycast.com/basics/publish-an-extension)
- [ESLint Configuration](https://developers.raycast.com/information/developer-tools/eslint)
- [Navigation API](https://developers.raycast.com/api-reference/user-interface/navigation)
- [useForm Hook](https://developers.raycast.com/utilities/react-hooks/useform)
- [useCachedPromise Hook](https://developers.raycast.com/utilities/react-hooks/usecachedpromise)
- [raycast/extensions GitHub Repository](https://github.com/raycast/extensions)
