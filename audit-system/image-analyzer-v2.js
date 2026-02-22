/**
 * Image Content Analyzer v2.0
 * Combines heuristics with OCR for accurate content detection
 */

const { OCRAnalyzer } = require('./ocr-analyzer');

class ImageAnalyzerV2 {
  constructor(config = {}) {
    this.ocr = new OCRAnalyzer(config.ocr || {});
    this.maxImages = config.maxImages || 10;
  }

  async analyzeImages(html, baseUrl) {
    const imageUrls = this.extractImageUrls(html, baseUrl);
    
    const analysis = {
      totalImages: imageUrls.length,
      analyzed: 0,
      withOCR: 0,
      byType: {
        schedule: [],
        menu: [],
        pricing: [],
        gallery: [],
        logo: [],
        unknown: []
      },
      criticalFindings: [],
      extractedData: {
        allPrices: [],
        allTimes: [],
        allDays: [],
        scheduleItems: [],
        menuItems: []
      }
    };

    console.log(`\n   📸 Found ${imageUrls.length} images, analyzing ${Math.min(imageUrls.length, this.maxImages)}...\n`);

    for (const imgUrl of imageUrls.slice(0, this.maxImages)) {
      const imgResult = await this.analyzeSingleImage(imgUrl, html);
      
      if (imgResult.contentType) {
        analysis.byType[imgResult.contentType]?.push(imgResult);
      } else {
        analysis.byType.unknown.push(imgResult);
      }

      // Aggregate extracted data
      if (imgResult.ocrResult?.detectedElements) {
        const el = imgResult.ocrResult.detectedElements;
        analysis.extractedData.allPrices.push(...el.prices);
        analysis.extractedData.allTimes.push(...el.times);
        analysis.extractedData.allDays.push(...el.days);
      }

      analysis.analyzed++;
      if (imgResult.ocrResult?.text) analysis.withOCR++;
    }

    // Generate critical findings
    this.generateFindings(analysis);

    return analysis;
  }

  async analyzeSingleImage(imgUrl, pageHtml) {
    const result = {
      url: imgUrl,
      fileName: this.extractFileName(imgUrl),
      altText: this.extractAltText(imgUrl, pageHtml),
      heuristicType: this.detectTypeByHeuristics(imgUrl, pageHtml),
      ocrResult: null,
      contentType: null,
      confidence: 0,
      recommendation: null
    };

    // Run OCR
    result.ocrResult = await this.ocr.analyzeImage(imgUrl);
    
    // Combine heuristic + OCR results
    if (result.ocrResult.contentType !== 'unknown') {
      result.contentType = result.ocrResult.contentType;
      result.confidence = result.ocrResult.confidence;
    } else {
      result.contentType = result.heuristicType;
      result.confidence = 0.6;
    }

    // Generate specific recommendation
    result.recommendation = this.generateRecommendation(result);

    return result;
  }

  detectTypeByHeuristics(imgUrl, html) {
    const filename = imgUrl.toLowerCase();
    const alt = (this.extractAltText(imgUrl, html) || '').toLowerCase();
    
    if (/schedule|timetable|class-times/i.test(filename + alt)) return 'schedule';
    if (/menu|food|breakfast|lunch|dinner/i.test(filename + alt)) return 'menu';
    if (/price|membership|rate/i.test(filename + alt)) return 'pricing';
    if (/logo|brand/i.test(filename + alt)) return 'logo';
    if (/gallery|photo|img/i.test(filename + alt)) return 'gallery';
    
    return 'unknown';
  }

  generateRecommendation(result) {
    switch (result.contentType) {
      case 'schedule':
        return {
          issue: 'Schedule is embedded in an image',
          impact: [
            'Search engines cannot read class times',
            'Screen readers cannot access schedule',
            'Mobile users cannot zoom text',
            'Hard to update (requires image editing)'
          ],
          solution: 'Convert to HTML table with structured data',
          priority: 'high'
        };
        
      case 'menu':
        return {
          issue: 'Menu is embedded in an image',
          impact: [
            'Items are not searchable on Google',
            'Prices cannot be updated easily',
            'Dietary info not accessible',
            'Poor mobile experience'
          ],
          solution: 'Create HTML menu with schema markup',
          priority: 'high'
        };
        
      case 'pricing':
        return {
          issue: 'Pricing is embedded in an image',
          impact: [
            'Prices not searchable',
            'Cannot update prices without editing image',
            'No comparison shopping visibility'
          ],
          solution: 'Use HTML pricing tables with clear CTAs',
          priority: 'medium'
        };
        
      default:
        return null;
    }
  }

  generateFindings(analysis) {
    // Schedule findings
    if (analysis.byType.schedule.length > 0) {
      const schedules = analysis.byType.schedule;
      analysis.criticalFindings.push({
        type: 'image_schedules',
        count: schedules.length,
        severity: 'high',
        summary: `Found ${schedules.length} image(s) containing class schedules`,
        details: schedules.map(s => ({
          file: s.fileName,
          confidence: Math.round(s.confidence * 100) + '%',
          extractedTimes: s.ocrResult?.detectedElements?.times?.slice(0, 5) || []
        })),
        businessImpact: 'Potential members searching for "yoga classes york pa" will not find your schedule',
        solution: 'Convert to interactive HTML schedule with filter/search'
      });
    }

    // Menu findings
    if (analysis.byType.menu.length > 0) {
      const menus = analysis.byType.menu;
      const allPrices = analysis.extractedData.allPrices;
      
      analysis.criticalFindings.push({
        type: 'image_menus',
        count: menus.length,
        severity: 'high',
        summary: `Found ${menus.length} image(s) containing menus`,
        details: menus.map(m => ({
          file: m.fileName,
          sampleItems: m.ocrResult?.text?.substring(0, 100) + '...'
        })),
        extractedPrices: [...new Set(allPrices)].slice(0, 10),
        businessImpact: 'Menu items not searchable; customers can\'t find dishes on Google',
        solution: 'Build HTML menu with item pages, photos, and online ordering'
      });
    }

    // Pricing findings
    if (analysis.byType.pricing.length > 0) {
      analysis.criticalFindings.push({
        type: 'image_pricing',
        count: analysis.byType.pricing.length,
        severity: 'medium',
        summary: 'Pricing information is image-based',
        solution: 'Use clear HTML pricing with prominent CTAs'
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

module.exports = { ImageAnalyzerV2 };
