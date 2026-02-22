---
name: website-audit
description: Comprehensive website auditing tool that analyzes HTML content, checks for broken pages, evaluates SEO and performance, and generates detailed reports with recommendations. Use when you need to evaluate a prospect's website for sales opportunities or create pitch materials.
metadata:
  {
    "openclaw":
      {
        "requires": { "bins": ["node"] },
        "allow": ["exec", "read"]
      },
  }
---

# Website Audit Skill

Run comprehensive website audits to identify sales opportunities and create pitch materials.

## Usage

```bash
# Run full audit
node /workspace/audit-system/run-audit.js <url>

# Example
node /workspace/audit-system/run-audit.js https://fitness1440.com/yorkpa/
```

## What It Checks

### Pages (14 types)
- Homepage, About, Contact
- Services, Menu, Products
- Pricing, Schedule, Classes
- Gallery, Reviews
- Book Now, Join, Memberships

### Analysis
- **SEO:** Titles, meta descriptions, headings, schema
- **Performance:** Load times, images, scripts
- **Accessibility:** Alt tags, semantic HTML
- **Mobile:** Viewport, responsive design
- **Broken Pages:** 404s, missing content
- **CMS Detection:** WordPress, Shopify, etc.

## Output

Generates reports in `/workspace/audit-system/reports/`:
- `.json` - Machine-readable data
- `.md` - Human-readable report with scores

## Example Report

```
Overall Score: 45/100
Working Pages: 3/14
Critical Issues: 5
High Priority: 3

Broken Pages:
- /about (404)
- /pricing (404)
- /memberships (404)

Recommendations:
- Fix 11 broken pages
- Add mobile viewport
- Optimize images
- Add call-to-action buttons
```

## Sales Pitch Use

Use audit results to create compelling proposals showing:
1. What's broken (lost revenue)
2. What's missing (missed opportunities)
3. Competitor comparison
4. Investment vs. ROI
