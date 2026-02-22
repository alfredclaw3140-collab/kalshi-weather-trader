#!/usr/bin/env node
const { ImageAnalyzer } = require('./image-analyzer');

async function test() {
  console.log('🔍 Testing Tesseract.js OCR Integration\n');
  console.log('='.repeat(60));
  
  // Create test HTML with realistic image URLs
  // Note: For real testing, you'd use actual image URLs
  const testHtml = `
    <html>
    <body>
      <h1>Fitness 1440 York</h1>
      
      <h2>Winter Class Schedule</h2>
      <img src="https://www.fitness1440.com/yorkpa/wp-content/uploads/schedule-winter-2024.jpg" 
           alt="Winter 2024 Class Schedule">
      
      <h2>Membership Options</h2>
      <img src="https://www.fitness1440.com/yorkpa/wp-content/uploads/membership-pricing.jpg" 
           alt="Membership Rates">
      
      <h2>Photo Gallery</h2>
      <img src="https://www.fitness1440.com/yorkpa/wp-content/uploads/gym-interior-1.jpg" 
           alt="Gym Interior">
    </body>
    </html>
  `;

  const analyzer = new ImageAnalyzer({ maxImages: 5 });
  
  try {
    const results = await analyzer.analyzeImages(testHtml, 'https://www.fitness1440.com/yorkpa/');

    console.log('\n📊 RESULTS\n');
    console.log(`Total Images Found: ${results.totalImages}`);
    console.log(`Analyzed with OCR: ${results.withOCR}`);
    console.log(`Errors: ${results.errors}\n`);

    // Show findings by type
    console.log('📁 CONTENT DETECTED:\n');
    for (const [type, images] of Object.entries(results.byType)) {
      if (images.length > 0) {
        console.log(`${type.toUpperCase()} (${images.length}):`);
        images.forEach(img => {
          console.log(`  📄 ${img.fileName}`);
          console.log(`     Confidence: ${Math.round(img.confidence * 100)}%`);
          
          if (img.ocrResult?.text) {
            const lines = img.ocrResult.text.split('\n').filter(l => l.trim());
            console.log(`     Extracted ${lines.length} lines of text`);
            
            // Show detected elements
            const el = img.ocrResult.detectedElements;
            if (el.prices.length > 0) console.log(`     💰 Prices: ${el.prices.join(', ')}`);
            if (el.times.length > 0) console.log(`     ⏰ Times: ${el.times.slice(0, 5).join(', ')}`);
            if (el.days.length > 0) console.log(`     📅 Days: ${el.days.join(', ')}`);
          }
          
          if (img.recommendation) {
            console.log(`     ⚠️ ${img.recommendation.issue}`);
          }
          console.log();
        });
      }
    }

    // Critical findings
    if (results.criticalFindings.length > 0) {
      console.log('🚨 CRITICAL FINDINGS:\n');
      results.criticalFindings.forEach(f => {
        console.log(`${f.type.toUpperCase()}:`);
        console.log(`  ${f.summary}`);
        console.log(`  Severity: ${f.severity}`);
        console.log(`  Business Impact: ${f.businessImpact}`);
        if (f.extractedData) {
          console.log(`  Extracted: ${JSON.stringify(f.extractedData, null, 2)}`);
        }
        console.log();
      });
    }

    console.log('='.repeat(60));
    console.log('✅ Tesseract.js OCR integration complete!');
    console.log('Ready to analyze real websites.');
    
  } catch (err) {
    console.error('Test failed:', err);
    process.exit(1);
  }
}

test();
