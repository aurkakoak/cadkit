# CadKit documentation

CadKit gives a CadQuery model named parts, assemblies, manufacturing information
and checks. You keep writing Python geometry and use CadKit to inspect it,
export it and work on it with an agent.

**Start with [Make a box and lid](tutorials/index.md).** The tutorial begins with
two ordinary CadQuery shapes. You will turn them into a project, inspect and
export the parts, fasten the lid, test a design change and give an agent a small
modelling task. Each section has a runnable example.

| What you need | Where to go |
| --- | --- |
| Learn by building something | [Box-and-lid tutorial](tutorials/index.md) |
| Complete a particular task | [How-to guides](how-to/index.md) |
| Understand the model and its limits | [Explanation](explanation/index.md) |
| Look up a constructor, method, command or file format | [Reference](reference/index.md) |

If you already have a project, go directly to [installation](how-to/install.md),
[adopting CadQuery code](how-to/adopt-cadquery.md) or
[connecting an agent](how-to/connect-an-agent.md).

Use `import cadkit as ck` to define parts, features and assemblies. Compile an
assembly with `as_project()` to open it in the desktop or CLI. See
[how CadQuery and CadKit fit together](explanation/cadquery-and-cadkit.md).
