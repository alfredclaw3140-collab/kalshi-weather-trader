# 🔍 Website Audit System

Comprehensive website auditing tool that combines HTML analysis with visual screenshot capture. Built for OpenClaw to help identify sales prospects and create compelling pitch materials.

## Features

### 📊 HTML Analysis
- **Page Coverage:** Checks 14+ common page types
- **SEO Audit:** Titles, meta descriptions, headings, schema, canonical URLs
- **Performance:** Load times, script count, image optimization
- **Accessibility:** Alt tags, semantic HTML
- **Mobile Responsiveness:** Viewport detection
- **Security:** Mixed content detection
- **CMS Detection:** WordPress, Shopify, Wix, etc.

### 📸 Visual Analysis
- **Multi-viewport Screenshots:** Desktop (1920x1080), Tablet (768x1024), Mobile (375x667)
- **Full-page Capture:** Not just viewport
- **Visual Regression:** Compare before/after (planned)

### 📈 Reporting
- **Overall Scores:** 0-100 grading
- **Priority Issues:** Critical, High, Medium, Low
- **Markdown Reports:** Human-readable with tables
- **JSON Reports:** Machine-parseable data

## Installation

```bash
# Navigate to audit system
cd audit-system

# Install dependencies (when screenshot capture is enabled)
npm install puppeteer pixelmatch pngjs
```

## Usage

### Basic Audit (HTML Analysis Only)

```bash
node run-audit.js https://example.com
```

### From OpenClaw

Once the skill is integrated, you can call:

```javascript
// Run full audit
audit("https://fitness1440.com/yorkpa/")

// Results include:
// - Overall score
// - Broken pages
// - SEO issues
// - Screenshot paths
// - Recommendations
```

## Output Structure

```
audit-system/
├── screenshots/
│   └── fitness1440.com/
│       ├── homepage-desktop.png
│       ├── homepage-tablet.png
│       ├── homepage-mobile.png
│       ├── about-desktop.png
│       └── ...
├── reports/
│   ├── fitness1440.com-audit-1708092345.json    # Machine readable
│   ├── fitness1440.com-audit-1708092345.md      # Human readable
│   └── fitness1440.com-full-audit.json          # Combined report
└── README.md
```

## Page Types Checked

| Page | Purpose | Priority |
|------|---------|----------|
| `/` | Homepage | Critical |
| `/about` | Company info | High |
| `/contact` | Contact details | High |
| `/services` | Service offerings | High |
| `/menu` | Restaurant menu | High |
| `/products` | Product catalog | High |
| `/pricing` | Pricing info | Critical |
| `/schedule` | Class/booking schedule | High |
| `/classes` | Class descriptions | Medium |
| `/gallery` | Photo gallery | Medium |
| `/reviews` | Testimonials | Medium |
| `/book-now` | Booking CTA | Critical |
| `/join` | Membership/signup | Critical |
| `/memberships` | Membership tiers | Critical |

## Scoring System

### Overall Score (0-100)
- **90-100:** Excellent, minor improvements only
- **70-89:** Good, some issues to address
- **50-69:** Fair, needs significant work
- **0-49:** Poor, complete overhaul recommended

### Category Scores

**SEO Score**
- Title tag present: +20
- Meta description: +20
- H1 heading: +20
- Alt tags on images: +20
- Canonical URL: +10
- Schema markup: +10

**Performance Score**
- Load time < 3s: Good
- Load time 3-5s: Needs work
- Load time > 5s: Critical
- Lazy loading images: +15
- WebP format: +10

**Mobile Score**
- Viewport meta: Required
- Responsive images: Bonus
- Touch targets: Bonus

## Issue Severity Levels

| Severity | Description | Example |
|----------|-------------|---------|
| 🔴 Critical | Breaking functionality | 404 pages, no viewport tag |
| 🟠 High | Major UX/SEO impact | Missing titles, no alt tags |
| 🟡 Medium | Should fix soon | Thin content, slow load |
| 🟢 Low | Nice to have | Missing schema, old CMS |

## Integration with OpenClaw

### Option 1: Direct Script Call

```javascript
const { runFullAudit } = require('./audit-system/run-audit');
const results = await runFullAudit('https://example.com');
```

### Option 2: CLI from Exec

```bash
node /workspace/audit-system/run-audit.js https://example.com
```

### Option 3: Skill Wrapper (Recommended)

Create a skill that calls the audit system and formats results for conversation.

## Sales Pitch Integration

Use audit results to create compelling pitches:

```markdown
## Your Website is Losing You Customers

Our audit found **{brokenPages} broken pages** on your site:
- Pricing page: 404 error
- Class schedule: Empty content
- Sign-up form: Not working

**You're missing an estimated {estimatedRevenue} in potential revenue.**

### What We Can Build

✅ Fully functional multi-page site  
✅ Online booking/membership system  
✅ Mobile-responsive design  
✅ SEO optimization  
✅ Photo gallery of your facility  

**Investment:** $X,XXX  
**Timeline:** 2-3 weeks  
**ROI:** Typically 5-10x within 6 months
```

## Future Enhancements

- [ ] Lighthouse CI integration
- [ ] WAVE accessibility testing
- [ ] GTmetrix/PageSpeed API
- [ ] Competitor comparison
- [ ] Visual diff tracking over time
- [ ] Automated prospect outreach

## License

MIT - Use freely for your agency work.
