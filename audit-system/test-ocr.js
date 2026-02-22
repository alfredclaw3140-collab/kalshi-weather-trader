#!/usr/bin/env node
const { ImageAnalyzerV2 } = require('./image-analyzer-v2');
const { OCRAnalyzer } = require('./ocr-analyzer');

async function testOCR() {
  console.log('🔍 Testing OCR Image Analysis\n');
  console.log('='.repeat(60));
  
  // Sample HTML with various image types
  const testHtml = `
    <html>
    <body>
      <h1>Fitness 1440 York</h1>
      
      <h2>Class Schedule</h2>
      <img src="class-schedule-winter-2024.jpg" alt="Winter Class Schedule">
      <img src="timetable-morning.jpg" alt="">
      
      <h2>Membership Pricing</h2>
      <img src="membership-rates.jpg" alt="Membership Options">
      
      <h2>Gallery</h2>
      <img src="gym-interior.jpg" alt="Gym Interior">
      <img src="trainer-photo.jpg" alt="Personal Trainer">
      
      <h2>Our Logo</h2>
      <img src="logo-white.png" alt="Fitness 1440 Logo">
    </body>
    </html>
  `;

  const analyzer = new ImageAnalyzerV2({ maxImages: 10 });
  const results = await analyzer.analyzeImages(testHtml, 'https://example.com');

  console.log('\n📊 RESULTS\n');
  console.log(`Total Images: ${results.totalImages}`);
  console.log(`Analyzed: ${results.analyzed}`);
  console.log(`With OCR: ${results.withOCR}\n`);

  // Show by type
  console.log('📁 BY CONTENT TYPE:\n');
  for (const [type, images] of Object.entries(results.byType)) {
    if (images.length > 0) {
      console.log(`${type.toUpperCase()} (${images.length}):`);
      images.forEach(img => {
        console.log(`  📄 ${img.fileName}`);
        console.log(`     Confidence: ${Math.round(img.confidence * 100)}%`);
        if (img.ocrResult?.text) {
          const preview = img.ocrResult.text.substring(0, 80).replace(/\n/g, ' ');
          console.log(`     OCR Preview: "${preview}..."`);
        }
        if (img.recommendation) {
          console.log(`     ⚠️ ${img.recommendation.issue}`);
        }
        console.log();
      });
    }
  }

  // Show critical findings
  if (results.criticalFindings.length > 0) {
    console.log('🚨 CRITICAL FINDINGS:\n');
    results.criticalFindings.forEach(finding => {
      console.log(`${finding.type.toUpperCase()}:`);
      console.log(`  ${finding.summary}`);
      console.log(`  Severity: ${finding.severity}`);
      console.log(`  Impact: ${finding.businessImpact}`);
      console.log(`  Solution: ${finding.solution}\n`);
    });
  }

  // Show extracted data
  console.log('💎 EXTRACTED DATA:\n');
  console.log(`Prices found: ${results.extractedData.allPrices.length}`);
  console.log(`Times found: ${results.extractedData.allTimes.length}`);
  console.log(`Days found: ${results.extractedData.allDays.length}`);
  
  if (results.extractedData.allPrices.length > 0) {
    console.log(`Unique prices: ${[...new Set(results.extractedData.allPrices)].join(', ')}`);
  }
  if (results.extractedData.allTimes.length > 0) {
    console.log(`Class times: ${[...new Set(results.extractedData.allTimes)].slice(0, 5).join(', ')}`);
  }

  console.log('\n' + '='.repeat(60));
  console.log('This is how OCR enables precise content analysis!');
  console.log('In production, use Tesseract.js (free) or Google Vision (accurate)');
}

testOCR().catch(console.error);
