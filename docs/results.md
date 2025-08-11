---
layout: default
title: Results
nav_order: 3
---

# Results

<p>Numbers are parsed from workload output (<code>Mean</code> and <code>Std Dev</code>). Speedup is <code>before.mean / after.mean</code>.</p>

<table>
  <thead>
    <tr>
      <th>Task</th>
      <th>Before (mean±std)</th>
      <th>Human (mean±std)</th>
      <th>LLM (mean±std)</th>
      <th>Speedup (human)</th>
      <th>Speedup (LLM)</th>
      <th>LLM better?</th>
      <th>Updated</th>
    </tr>
  </thead>
  <tbody>
  {% assign R = site.data.results %}
  {% for r in R %}
    <tr>
      <td><code>{{ r.id }}</code></td>
      <td>
        {% if r.before %}
          {{ r.before.mean }} ± {{ r.before.std }}
        {% else %} — {% endif %}
      </td>
      <td>
        {% if r.after_human %}
          {{ r.after_human.mean }} ± {{ r.after_human.std }}
        {% else %} — {% endif %}
      </td>
      <td>
        {% if r.after_llm %}
          {{ r.after_llm.mean }} ± {{ r.after_llm.std }}
        {% else %} — {% endif %}
      </td>
      <td>{{ r.speedup_human | default: "—" }}</td>
      <td>{{ r.speedup_llm | default: "—" }}</td>
      <td>{{ r.comparison.llm_better | default: "UNKNOWN" }}</td>
      <td>{{ r.updated_at | default: "—" }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>

