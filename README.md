# nomoreslop

Agent skills for website content, UX, interface design, typography, color systems, motion, and 3D visuals. The workflow starts with the visitor's task and real content, then develops information structure, composition, visual detail, and working interactions.

| Skill | Use it for |
| --- | --- |
| [nomoreslop](skills/nomoreslop/SKILL.md) | Coordinate the specialists around one shared brief |
| [nomoreslop-writing](skills/nomoreslop-writing/SKILL.md) | Page content, product voice, actions, forms, and interface states |
| [nomoreslop-ux](skills/nomoreslop-ux/SKILL.md) | Information architecture, task-based layout, navigation, controls, states, and usability review |
| [nomoreslop-design](skills/nomoreslop-design/SKILL.md) | Art direction, composition, typography, motion, and review for websites, web apps, and desktop/mobile interfaces |
| [nomoreslop-typography](skills/nomoreslop-typography/SKILL.md) | Readability, hierarchy, spacing, multilingual text, and font research |
| [nomoreslop-color](skills/nomoreslop-color/SKILL.md) | Palette and gradient research, semantic color roles, and paired light/dark proposals |
| [nomoreslop-motion](skills/nomoreslop-motion/SKILL.md) | Interaction and scroll behavior, motion direction, interruption, lifecycle, and performance checks |
| [nomoreslop-3d](skills/nomoreslop-3d/SKILL.md) | Subjects, models, materials, animation, and scene performance |

## Install

With Node.js and the [Skills CLI](https://skills.sh/docs/cli):

```sh
npx skills add grodionn/nomoreslop
```

Select all eight skills for the complete workflow. To install only design in a Codex project:

```sh
npx skills add grodionn/nomoreslop --skill nomoreslop-design --agent codex
```

Add `--global` to install across projects. Private deployments require GitHub access.

Alternatively, clone the repository and use Python 3.10+ without third-party packages:

```sh
git clone https://github.com/grodionn/nomoreslop.git
cd nomoreslop
python scripts/install_skill.py --skill nomoreslop
python scripts/install_skill.py --skill nomoreslop-writing
python scripts/install_skill.py --skill nomoreslop-design
python scripts/install_skill.py --skill nomoreslop-3d
python scripts/install_skill.py --skill nomoreslop-typography
python scripts/install_skill.py --skill nomoreslop-color
python scripts/install_skill.py --skill nomoreslop-motion
python scripts/install_skill.py --skill nomoreslop-ux
```

The local installer copies one skill to `~/.agents/skills/<skill>` and refuses to overwrite an existing installation. Use `--project <path>` for a project's `.agents/skills` directory. Without `--skill`, it installs design. Install the specialists alongside the coordinator.

## Use

```text
Use $nomoreslop to redesign this page. The audience is ...,
the main action is ..., and these are the materials to preserve: ...
Write the interface copy in English.
```

Use the individual specialists directly for a focused task, including `$nomoreslop-ux` for a usability audit and `$nomoreslop-motion` for an interaction or scroll problem. Include existing materials, constraints, and decisions you want to delegate. The coordinator shares one brief between specialists and brings in 3D when the task calls for it.

The design skill includes revision 27: resource research and selection, shared interface rules, project-state tracking, platform workflows, and targeted regression checks.

UX establishes tasks, information relationships, priorities, functional layout, controls, and states before a new structure is fixed. Design integrates those decisions into the visual composition. The UX reference library covers 27 interface families with task-specific branches; it does not impose one layout or visual style on every product. Motion handles timing, lifecycle, interruption, reduced motion, and execution evidence. Both specialists support focused work without requiring a full redesign.

Typography covers reading conditions, text roles, spacing, identity, language coverage, and open-font research. Color researches relevant Colorsinspo palette, gradient, and solid-color sections, plus available Refero material. Each new palette proposal includes related light/dark roles; implementing a theme switch remains scoped to the request. Refero live MCP access requires separate authorization and a paid plan.

## Language and scope

The README and contributor documentation are in English. Skill instructions, reference libraries, and behavior scenarios are currently in Russian. Specify the target language and locale in your prompt; a full English translation of the skill library is still pending.

The package contains instructions, reference material, Python tools, and tests. Automated checks validate the tools and package structure; they do not establish design quality or demonstrate an improvement over an agent without these skills.

## Documentation

- [Usage guidance](docs/BEST_PRACTICES.md)
- [Testing and limitations](docs/TESTING.md)
- [Contributing](CONTRIBUTING.md)
- [Interface writing research (Russian)](skills/nomoreslop-writing/references/research.md)

[MIT license](LICENSE).
