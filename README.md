# nomoreslop

Agent skills for website content, interface design, and 3D visuals. The workflow starts with the visitor's task and real content, then develops composition, visual detail, and working interactions.

| Skill | Use it for |
| --- | --- |
| [nomoreslop](skills/nomoreslop/SKILL.md) | Coordinate the specialists around one shared brief |
| [nomoreslop-writing](skills/nomoreslop-writing/SKILL.md) | Page content, product voice, actions, forms, and interface states |
| [nomoreslop-design](skills/nomoreslop-design/SKILL.md) | Art direction, composition, typography, motion, and review for websites, web apps, and desktop/mobile interfaces |
| [nomoreslop-3d](skills/nomoreslop-3d/SKILL.md) | Subjects, models, materials, animation, and scene performance |

## Install

With Node.js and the [Skills CLI](https://skills.sh/docs/cli):

```sh
npx skills add grodionn/nomoreslop
```

Select all four skills for the complete workflow. To install only design in a Codex project:

```sh
npx skills add grodionn/nomoreslop --skill nomoreslop-design --agent codex
```

Add `--global` to install across projects. This repository is currently private; GitHub access is required.

Alternatively, clone the repository and use Python 3.10+ without third-party packages:

```sh
git clone https://github.com/grodionn/nomoreslop.git
cd nomoreslop
python scripts/install_skill.py --skill nomoreslop
python scripts/install_skill.py --skill nomoreslop-writing
python scripts/install_skill.py --skill nomoreslop-design
python scripts/install_skill.py --skill nomoreslop-3d
```

The local installer copies one skill to `~/.agents/skills/<skill>` and refuses to overwrite an existing installation. Use `--project <path>` for a project's `.agents/skills` directory. Without `--skill`, it installs design. Install the specialists alongside the coordinator.

## Use

```text
Use $nomoreslop to redesign this page. The audience is ...,
the main action is ..., and these are the materials to preserve: ...
Write the interface copy in English.
```

Use `$nomoreslop-writing`, `$nomoreslop-design`, or `$nomoreslop-3d` directly for a focused task. Include existing materials, constraints, and decisions you want to delegate. The coordinator shares the brief between specialists and brings in 3D when the task calls for it.

The design skill includes revision 17: resource research and selection, project-state tracking, platform workflows, and targeted regression checks.

## Language and scope

The README and contributor documentation are in English. Skill instructions, reference libraries, and behavior scenarios are currently in Russian. Specify the target language and locale in your prompt; a full English translation of the skill library is still pending.

The package contains instructions, reference material, Python tools, and tests. Automated checks validate the tools and package structure; they do not establish design quality or demonstrate an improvement over an agent without these skills.

## Documentation

- [Usage guidance](docs/BEST_PRACTICES.md)
- [Testing and limitations](docs/TESTING.md)
- [Contributing](CONTRIBUTING.md)
- [Interface writing research (Russian)](skills/nomoreslop-writing/references/research.md)

[MIT license](LICENSE).
