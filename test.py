#!/usr/bin/env python3
import os
import sys
import pdfplumber


def extract_pdf_text(pdf_path):
    """Extract text from PDF file using pdfplumber"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            num_pages = len(pdf.pages)
            print(f"PDF文件包含 {num_pages} 页")
            all_text = ""
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    all_text += f"\n=== 第 {i + 1} 页 ===\n{text}\n"
                else:
                    all_text += f"\n=== 第 {i + 1} 页 ===\n(无文本内容或扫描图像)\n"

            return all_text

    except Exception as e:
        return f"读取PDF文件时出错: {str(e)}"

if __name__ == "__main__":

    # if len(sys.argv) != 2:
    #      print("用法: python extract_pdf2.py <pdf文件路径>")
    #      sys.exit(1)

    # pdf_path = sys.argv[1]
    pdf_path ="C://Users//EDY//Downloads//biaoyang.pdf"
    print(f"正在处理文件: {pdf_path}")
    text = extract_pdf_text(pdf_path)
    print(text)