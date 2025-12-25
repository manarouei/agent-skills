#!/bin/bash
# Quick translation command aliases
# Source this file: source quick_translate.sh

# Set your API key (or set it in your .bashrc/.zshrc)
export OPENAI_API_KEY="${OPENAI_API_KEY:-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}"

# Quick translation function
translate() {
    if [ $# -lt 2 ]; then
        echo "Usage: translate 'text' target_language"
        echo ""
        echo "Examples:"
        echo "  translate 'Hello' Spanish"
        echo "  translate 'خرسهای کثیف' English"
        echo "  translate 'Bonjour' English"
        return 1
    fi
    
    make run-skill NAME=openai.translate INPUT="$1" TARGET_LANG="$2" 2>&1 | grep -v "^{"
}

# Language-specific shortcuts
to_english() {
    translate "$1" English
}

to_spanish() {
    translate "$1" Spanish
}

to_persian() {
    translate "$1" Persian
}

to_arabic() {
    translate "$1" Arabic
}

to_french() {
    translate "$1" French
}

echo "✅ Translation commands loaded!"
echo ""
echo "Available commands:"
echo "  translate 'text' language  - Translate to any language"
echo "  to_english 'text'          - Translate to English"
echo "  to_spanish 'text'          - Translate to Spanish"
echo "  to_persian 'text'          - Translate to Persian"
echo "  to_arabic 'text'           - Translate to Arabic"
echo "  to_french 'text'           - Translate to French"
echo ""
echo "Examples:"
echo "  translate 'Hello' Spanish"
echo "  to_english 'خرسهای کثیف به تو می اندیشند'"
echo "  to_persian 'I love programming'"
