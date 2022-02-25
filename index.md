---
layout: home
title: Gaussian Process Summer School Lectures
---

This is a repository for various lectures for the [Gaussian Process Summer School](http://gpss.cc). 

These lectures are currently in *DRAFT* form as they are rewritten with parallel notebooks.

## Lectures

{% assign lastone = site.lectures | last %}
{% for lecture in site.lectures %}
{% include listlecture.html %}
{% endfor %}

