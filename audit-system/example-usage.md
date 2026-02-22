# Example Usage: Auditing Local Businesses

## Scenario 1: Fitness 1440 York, PA

```bash
# Run the audit
./quick-audit.sh https://www.fitness1440.com/yorkpa/

# Output:
🔍 Starting comprehensive audit for: https://www.fitness1440.com/yorkpa/

Phase 1: Analyzing HTML content...
  📄 Checking: homepage (https://www.fitness1440.com/yorkpa/)
  📄 Checking: about (https://www.fitness1440.com/yorkpa/about/)
  ❌ Page returned 404
  📄 Checking: contact (https://www.fitness1440.com/yorkpa/contact/)
  📄 Checking: memberships (https://www.fitness1440.com/yorkpa/memberships/)
  ❌ Page returned 404
  ...

==================================================
📊 AUDIT COMPLETE
==================================================
Overall Score: 32/100
Working Pages: 3/14
Screenshots Planned: 3
Critical Issues: 11
High Priority: 4

Reports saved to: ./reports/
==================================================
```

## Sales Pitch from Audit

**Subject:** Your Website is Costing You Memberships

Hi [Owner Name],

I was researching gyms in York and found Fitness 1440. Your facility looks great, but I noticed some issues with your website that might be hurting your business:

**🚨 Critical Issues Found:**
- 11 pages return "404 Not Found" errors
- No pricing information available
- Class schedule page is empty
- No way to sign up or book online

**💰 The Cost:**
Every day your website is broken, potential members are going to your competitors. Based on typical gym conversion rates, this could be costing you 5-10 new memberships per month.

**✅ What We Can Build:**
- Fully functional 10-page website
- Online membership signup
- Class schedule with booking
- Photo gallery of your facility
- Mobile-responsive design
- SEO optimization for "gym York PA"

**Investment:** $3,500  
**Timeline:** 2 weeks  
**Guarantee:** 50% more leads in 60 days or we work for free

Can we schedule 15 minutes to discuss? I can show you exactly what's wrong and how we'd fix it.

Best,  
[Your Name]

---

## Scenario 2: Restaurant Audit

```bash
./quick-audit.sh https://local-restaurant-york.com
```

**Key Findings to Pitch:**
- Menu not mobile-friendly (customers can't read on phones)
- No online ordering/reservations
- Photos are 5+ years old
- No Google Maps integration
- Missing hours on weekends

**ROI Angle:**
"Restaurants with online ordering see 30% higher ticket averages. With your current traffic, that's an extra $X,XXX per month."

---

## Batch Auditing Multiple Prospects

Create a list of targets:

```bash
# targets.txt
https://gym1-york.com
https://restaurant-downtown-york.com
https://york-fitness-center.com
https://local-cafe-york.com
```

Run batch audit:

```bash
while read url; do
    ./quick-audit.sh "$url"
done < targets.txt
```

Then sort results by score to prioritize outreach:
- 0-30 score: Hot prospects (broken sites)
- 31-60 score: Warm prospects (needs work)
- 61-90 score: Cold prospects (good enough)

---

## Using Reports in Meetings

1. **Open the markdown report** in your browser
2. **Screenshots show visual issues** clearly
3. **Score breakdown** demonstrates expertise
4. **Recommendations** become your proposal

**Example conversation:**

> "As you can see from the audit, your site scored 32 out of 100. The biggest issue is that 11 of your 14 most important pages are completely broken. Let me show you... [open screenshots]"

---

## Pricing Based on Audit Severity

| Audit Score | Condition | Your Price | Timeline |
|-------------|-----------|------------|----------|
| 0-30 | Broken/Missing | $3,000-5,000 | 2-3 weeks |
| 31-50 | Poor/Dated | $2,000-4,000 | 1-2 weeks |
| 51-70 | Needs Work | $1,500-3,000 | 1 week |
| 71-90 | Minor Issues | $500-1,500 | 2-3 days |
