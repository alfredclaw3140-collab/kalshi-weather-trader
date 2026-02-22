#!/usr/bin/env node
const { WebsiteAuditor } = require('./audit');

const url = process.argv[2];
if (!url) {
  console.log('Usage: node run-audit.js <url>');
  process.exit(1);
}

new WebsiteAuditor(url).run().then(results => {
  console.log('\n' + '='.repeat(50));
  console.log('📊 AUDIT COMPLETE');
  console.log('='.repeat(50));
  console.log(`Pages: ${results.summary.working}/${results.summary.total} working`);
  console.log(`Critical: ${results.summary.issues.critical.length}`);
  console.log(`High: ${results.summary.issues.high.length}`);
  console.log(`Medium: ${results.summary.issues.medium.length}`);
  console.log('='.repeat(50));
}).catch(err => {
  console.error('Audit failed:', err);
  process.exit(1);
});
