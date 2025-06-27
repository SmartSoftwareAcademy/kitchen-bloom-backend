#!/usr/bin/env python3
"""
Script to fix Unicode characters in Python files that cause encoding errors on Windows.
"""

import os
import re
import glob

def fix_unicode_in_file(filepath):
    """Fix Unicode characters in a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace common Unicode characters that cause issues
        replacements = {
            '→': '->',  # Right arrow
            '←': '<-',  # Left arrow
            '²': '2',   # Superscript 2
            '³': '3',   # Superscript 3
            '°': 'deg', # Degree symbol
            '×': 'x',   # Multiplication sign
            '÷': '/',   # Division sign
            '±': '+/-', # Plus-minus sign
            '≤': '<=',  # Less than or equal
            '≥': '>=',  # Greater than or equal
            '≠': '!=',  # Not equal
            '∞': 'inf', # Infinity
            '√': 'sqrt', # Square root
            'π': 'pi',  # Pi
            'α': 'alpha', # Alpha
            'β': 'beta',  # Beta
            'γ': 'gamma', # Gamma
            'δ': 'delta', # Delta
            'ε': 'epsilon', # Epsilon
            'θ': 'theta', # Theta
            'λ': 'lambda', # Lambda
            'μ': 'mu',   # Mu
            'σ': 'sigma', # Sigma
            'φ': 'phi',  # Phi
            'ω': 'omega', # Omega
        }
        
        original_content = content
        for unicode_char, ascii_replacement in replacements.items():
            content = content.replace(unicode_char, ascii_replacement)
        
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed Unicode characters in: {filepath}")
            return True
        return False
        
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Main function to fix Unicode characters in all Python files."""
    # Get all Python files in the backend directory
    python_files = glob.glob('**/*.py', recursive=True)
    
    fixed_count = 0
    for filepath in python_files:
        if fix_unicode_in_file(filepath):
            fixed_count += 1
    
    print(f"\nFixed Unicode characters in {fixed_count} files.")

if __name__ == '__main__':
    main() 