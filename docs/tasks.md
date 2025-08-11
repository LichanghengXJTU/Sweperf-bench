
---

## `docs/tasks.md`

```markdown
---
layout: default
title: Tasks
nav_order: 2
---

# Tasks

<table>
  <thead>
    <tr>
      <th>Task</th>
      <th>Repo</th>
      <th>Human</th>
      <th>LLM</th>
      <th>If LLM better</th>
    </tr>
  </thead>
  <tbody>
  {% assign task_map = site.data.tasks %}
  {% for pair in task_map %}
    {% assign key = pair[0] %}
    {% assign t = pair[1] %}
    <tr>
      <td><code>{{ t.id }}</code></td>
      <td>
        {% if t.repo.url and t.repo.name %}
          <a href="{{ t.repo.url }}">{{ t.repo.org }}/{{ t.repo.name }}</a>
        {% else %}
          —
        {% endif %}
      </td>
      <td>{{ t.status.human | default: "PENDING" }}</td>
      <td>
        {% if t.status.llm == "COMING_SOON" or t.docker.llm_image == "PLACEHOLDER" %}
          Coming soon
        {% else %}
          {{ t.status.llm }}
        {% endif %}
      </td>
      <td>{{ t.comparison.llm_better | default: "UNKNOWN" }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>


