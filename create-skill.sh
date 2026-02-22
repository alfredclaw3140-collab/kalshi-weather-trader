#!/bin/bash
#
# create-skill.sh - CLI tool to scaffold new OpenClaw skills
# Usage: ./create-skill.sh <skill-name> "Description of what it does"
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check args
if [ $# -lt 2 ]; then
    echo -e "${RED}Error: Missing arguments${NC}"
    echo "Usage: ./create-skill.sh <skill-name> \"Description of what it does\""
    echo ""
    echo "Examples:"
    echo "  ./create-skill.sh weather-checker \"Check local weather and forecasts\""
    echo "  ./create-skill.sh todo-manager \"Manage daily todo lists\""
    exit 1
fi

SKILL_NAME="$1"
DESCRIPTION="$2"
SKILL_DIR="skills/$SKILL_NAME"

echo -e "${BLUE}🔨 Creating new skill: $SKILL_NAME${NC}"
echo ""

# Check if skill already exists
if [ -d "$SKILL_DIR" ]; then
    echo -e "${RED}❌ Error: Skill '$SKILL_NAME' already exists${NC}"
    echo "   Location: $SKILL_DIR"
    exit 1
fi

# Create directory structure
mkdir -p "$SKILL_DIR"
echo -e "${GREEN}✓${NC} Created directory: $SKILL_DIR"

# Generate SKILL.md
cat > "$SKILL_DIR/SKILL.md" << SKILLMD
---
name: $SKILL_NAME
description: $DESCRIPTION
metadata:
  {
    "openclaw":
      {
        "requires": { "bins": [] },
        "allow": ["exec", "read"]
      }
  }
---

# $SKILL_NAME

$DESCRIPTION

## Usage

\`\`\`bash
# Example usage
./$SKILL_NAME.sh <arguments>
\`\`\`

## Examples

- Example 1: Describe what it does
- Example 2: Another use case

## Requirements

- List any required binaries or tools
- Note any API keys needed

## Output

Describe what the skill returns or creates.
SKILLMD

echo -e "${GREEN}✓${NC} Created SKILL.md"

# Create basic script template
cat > "$SKILL_DIR/$SKILL_NAME.sh" << 'SCRIPT'
#!/bin/bash
#
# Main script for SKILL_NAME
#

set -e

echo "Running SKILL_NAME..."
echo "Arguments: $@"

# Add your logic here

echo "Done!"
SCRIPT

# Replace placeholder with actual skill name
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/SKILL_NAME/$SKILL_NAME/g" "$SKILL_DIR/$SKILL_NAME.sh"
else
    sed -i "s/SKILL_NAME/$SKILL_NAME/g" "$SKILL_DIR/$SKILL_NAME.sh"
fi

chmod +x "$SKILL_DIR/$SKILL_NAME.sh"
echo -e "${GREEN}✓${NC} Created $SKILL_NAME.sh"

# Create README for the skill
cat > "$SKILL_DIR/README.md" << READMEMD
# $SKILL_NAME

$DESCRIPTION

## Installation

This skill is automatically available to the OpenClaw agent.

## Development

To modify this skill:
1. Edit SKILL.md for documentation
2. Edit $SKILL_NAME.sh for functionality
3. Test your changes
4. Commit to git

## TODO

- [ ] Implement core functionality
- [ ] Add error handling
- [ ] Write tests
- [ ] Update documentation
READMEMD

echo -e "${GREEN}✓${NC} Created README.md"

echo ""
echo -e "${GREEN}✅ Skill '$SKILL_NAME' created successfully!${NC}"
echo ""
echo -e "${YELLOW}📁 Location:${NC} $SKILL_DIR/"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Edit: $SKILL_DIR/SKILL.md"
echo "  2. Code: $SKILL_DIR/$SKILL_NAME.sh"
echo "  3. Test: ./$SKILL_DIR/$SKILL_NAME.sh"
echo "  4. Reload OpenClaw to use the skill"
echo ""
echo -e "${YELLOW}Tip:${NC} Add required binaries to SKILL.md metadata"
echo "  Example: \"requires\": { \"bins\": [\"node\", \"curl\"] }"
