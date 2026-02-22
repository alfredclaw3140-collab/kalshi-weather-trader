/**
 * Image Content Analyzer v2.0
 * Uses Tesseract.js OCR to verify actual image content
 */

const { OCRAnalyzer } = require('./ocr-analyzer');

class ImageAnalyzer {
  constructor(config = {}) {
    this.ocr = new OCRAnalyzer({ provider: 'tesseract' });
    this.maxImages = config.maxImages || 10;
  }

  async analyzeImages(html, baseUrl) {
    const imageUrls = this.extractImageUrls(html, baseUrl);
    
    const analysis = {
      totalImages: imageUrls.length,
      analyzed: 0,
      withOCR: 0,
      errors: 0,
      byType: { schedule: [], menu: [], pricing: [], gallery: [], logo: [], unknown: [] },
      criticalFindings: [],
      extractedData: { allPrices: [], allTimes: [], allDays: [], allItems: [] }
    };

    console.log(`\n   📸 Found ${imageUrls.length} images, analyzing up to ${this.maxImages} with OCR...\n`);

    for (const imgUrl of imageUrls.slice(0, this.maxImages)) {
      try {
        const imgResult = await this.analyzeSingleImage(imgUrl, html);
        
        if (imgResult.contentType && analysis.byType[imgResult.contentType]) {
          analysis.byType[imgResult.contentType].push(imgResult);
        } else {
          analysis.byType.unknown.push(imgResult);
        }

        // Aggregate data safely
        if (imgResult.ocrResult?.detectedElements) {
          const el = imgResult.ocrResult.detectedElements;
          if (el.prices) analysis.extractedData.allPrices.push(...el.prices);
          if (el.times) analysis.extractedData.allTimes.push(...el.times);
          if (el.days) analysis.extractedData.allDays.push(...el.days);
        }

        analysis.analyzed++;
        if (imgResult.ocrResult?.text) analysis.withOCR++;
        
      } catch (err) {
        console.error(`   ❌ Failed to analyze ${imgUrl}:`, err.message);
        analysis.errors++;
      }
    }

    this.generateFindings(analysis);
    return analysis;
  }

  async analyzeSingleImage(imgUrl, pageHtml) {
    const result = {
      url: imgUrl,
      fileName: this.extractFileName(imgUrl),
      altText: this.extractAltText(imgUrl, pageHtml),
      ocrResult: null,
      contentType: null,
      confidence: 0,
      recommendation: null
    };

    // Run OCR
    result.ocrResult = await this.ocr.analyzeImage(imgUrl);
    
    // Determine content type from OCR
    if (result.ocrResult.contentType !== 'unknown') {
      result.contentType = result.ocrResult.contentType;
      result.confidence = result.ocrResult.confidence;
    } else {
      // Fallback to heuristics
      result.contentType = this.detectTypeByHeuristics(imgUrl, pageHtml);
      result.confidence = 0.5;
    }

    result.recommendation = this.generateRecommendation(result);
    return result;
  }

  detectTypeByHeuristics(imgUrl, html) {
    const filename = imgUrl.toLowerCase();
    const alt = (this.extractAltText(imgUrl, html) || '').toLowerCase();
    const combined = filename + ' ' + alt;
    
    if (/schedule|timetable|class-times/i.test(combined)) return 'schedule';
    if (/menu|food|breakfast|lunch|dinner/i.test(combined)) return 'menu';
    if (/price|membership|rate/i.test(combined)) return 'pricing';
    if (/logo|brand/i.test(combined)) return 'logo';
    if (/gallery|photo|img/i.test(combined)) return 'gallery';
    
    return 'unknown';
  }

  generateRecommendation(result) {
    switch (result.contentType) {
      case 'schedule':
        return {
          issue: 'Schedule is embedded in an image',
          impact: [
            'Google cannot index class times',
            'Screen readers cannot read schedule',
            'Mobile users cannot zoom text',
            'Updates require image editing'
          ],
          solution: 'Convert to HTML table with structured data',
          priority: 'high',
          roi: 'Capture search traffic for "yoga classes 6am york pa" etc.'
        };
      case 'menu':
        return {
          issue: 'Menu is embedded in an image',
          impact: ['Not searchable', 'Not accessible', 'Hard to update'],
          solution: 'Create HTML menu with schema markup',
          priority: 'high'
        };
      case 'pricing':
        return {
          issue: 'Pricing is in an image',
          impact: ['Not searchable', 'Cannot update easily'],
          solution: 'Use HTML pricing tables',
          priority: 'medium'
        };
      default:
        return null;
    }
  }

  generateFindings(analysis) {
    // Schedule findings
    if (analysis.byType.schedule.length > 0) {
      const allTimes = [...new Set(analysis.extractedData.allTimes || [])];
      const allDays = [...new Set(analysis.extractedData.allDays || [])];
      
      analysis.criticalFindings.push({
        type: 'image_schedules',
        count: analysis.byType.schedule.length,
        severity: 'high',
        summary: `Found ${analysis.byType.schedule.length} schedule image(s)`,
        extractedData: {
          classTimes: allTimes.slice(0, 10),
          days: allDays,
          totalTimes: allTimes.length
        },
        businessImpact: `Missing SEO for ${allTimes.length} class times. People searching "yoga 6am york" won't find you.`,
        solution: 'Convert to searchable HTML schedule'
      });
    }

    // Menu findings
    if (analysis.byType.menu.length > 0) {
      const prices = [...new Set(analysis.extractedData.allPrices || [])];
      analysis.criticalFindings.push({
        type: 'image_menus',
        count: analysis.byType.menu.length,
        severity: 'high',
        extractedPrices: prices,
        businessImpact: 'Menu items not searchable on Google',
        solution: 'Build HTML menu with individual item pages'
      });
    }

    // Pricing findings
    if (analysis.byType.pricing.length > 0) {
      const prices = [...new Set(analysis.extractedData.allPrices || [])];
      analysis.criticalFindings.push({
        type: 'image_pricing',
        count: analysis.byType.pricing.length,
        severity: 'medium',
        extractedPrices: prices,
        solution: 'HTML pricing with clear CTAs'
      });
    }
  }

  extractImageUrls(html, baseUrl) {
    const urls = [];
    const regex = /<img[^>]+src=["']([^"']+)["'][^>]*>/gi;
    let match;
    
    while ((match = regex.exec(html)) !== null) {
      let url = match[1];
      
      if (url.startsWith('//')) url = 'https:' + url;
      else if (url.startsWith('/')) {
        const base = new URL(baseUrl);
        url = base.origin + url;
      } else if (!url.startsWith('http')) {
        url = baseUrl.replace(/\/$/, '') + '/' + url;
      }
      
      urls.push(url);
    }
    
    return [...new Set(urls)];
  }

  extractFileName(url) {
    try {
      return new URL(url).pathname.split('/').pop() || 'unknown';
    } catch {
      return url.split('/').pop() || 'unknown';
    }
  }

  extractAltText(imgUrl, html) {
    const escaped = imgUrl.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`<img[^>]*src=["']${escaped}["'][^>]*alt=["']([^"]*)["']`, 'i');
    const match = html.match(regex);
    return match ? match[1] : null;
  }
}

module.exports = { ImageAnalyzer };
