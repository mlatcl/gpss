---
layout: home
title: Gaussian Process Summer Schoool Lectures
---

This is a repository for various lectures for the [Gaussian Process Summer School](http://gpss.cc).

## Lectures

{% assign lastone = site.lectures | last %}
{% for lecture in site.lectures %}
{% include listlecture.html %}
{% endfor %}

