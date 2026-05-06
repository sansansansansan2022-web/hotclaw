/** Pixel Font System - 像素艺术字体系统
 *
 * 提供自定义的像素字体渲染，替代浏览器默认字体
 * 支持多种字体大小和样式，保持一致的像素艺术风格
 */

// 像素字体字符映射表 (8x8 像素)
const PIXEL_FONT_CHARS: Record<string, number[][]> = {
  // 数字 0-9
  '0': [
    [0,1,1,1,1,0],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [0,1,1,1,1,0]
  ],
  '1': [
    [0,0,1,0,0,0],
    [0,1,1,0,0,0],
    [0,0,1,0,0,0],
    [0,0,1,0,0,0],
    [0,0,1,0,0,0],
    [1,1,1,1,1,1]
  ],
  '2': [
    [0,1,1,1,1,0],
    [1,0,0,0,0,1],
    [0,0,0,0,0,1],
    [0,0,0,0,1,0],
    [0,0,0,1,0,0],
    [1,1,1,1,1,1]
  ],
  '3': [
    [0,1,1,1,1,0],
    [1,0,0,0,0,1],
    [0,0,0,0,0,1],
    [0,0,1,1,1,0],
    [0,0,0,0,0,1],
    [1,0,0,0,0,1],
    [0,1,1,1,1,0]
  ],
  '4': [
    [0,0,0,0,1,0],
    [0,0,0,1,1,0],
    [0,0,1,0,1,0],
    [0,1,0,0,1,0],
    [1,1,1,1,1,1],
    [0,0,0,0,1,0]
  ],
  '5': [
    [1,1,1,1,1,1],
    [1,0,0,0,0,0],
    [1,1,1,1,1,0],
    [0,0,0,0,0,1],
    [0,0,0,0,0,1],
    [1,0,0,0,0,1],
    [0,1,1,1,1,0]
  ],
  '6': [
    [0,0,1,1,1,0],
    [0,1,0,0,0,0],
    [1,0,0,0,0,0],
    [1,1,1,1,1,0],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [0,1,1,1,1,0]
  ],
  '7': [
    [1,1,1,1,1,1],
    [0,0,0,0,0,1],
    [0,0,0,0,1,0],
    [0,0,0,1,0,0],
    [0,0,1,0,0,0],
    [0,0,1,0,0,0]
  ],
  '8': [
    [0,1,1,1,1,0],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [0,1,1,1,1,0],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [0,1,1,1,1,0]
  ],
  '9': [
    [0,1,1,1,1,0],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [0,1,1,1,1,1],
    [0,0,0,0,0,1],
    [0,0,0,0,1,0],
    [0,1,1,1,0,0]
  ],
  
  // 字母 A-Z
  'A': [
    [0,0,1,1,1,0],
    [0,1,0,0,0,1],
    [0,1,0,0,0,1],
    [0,1,1,1,1,1],
    [0,1,0,0,0,1],
    [0,1,0,0,0,1]
  ],
  'B': [
    [1,1,1,1,1,0],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,1,1,1,1,0],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,1,1,1,1,0]
  ],
  'C': [
    [0,0,1,1,1,1],
    [0,1,0,0,0,0],
    [1,0,0,0,0,0],
    [1,0,0,0,0,0],
    [1,0,0,0,0,0],
    [0,1,0,0,0,0],
    [0,0,1,1,1,1]
  ],
  'D': [
    [1,1,1,1,1,0],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,1,1,1,1,0]
  ],
  'E': [
    [1,1,1,1,1,1],
    [1,0,0,0,0,0],
    [1,0,0,0,0,0],
    [1,1,1,1,1,0],
    [1,0,0,0,0,0],
    [1,0,0,0,0,0],
    [1,1,1,1,1,1]
  ],
  'F': [
    [1,1,1,1,1,1],
    [1,0,0,0,0,0],
    [1,0,0,0,0,0],
    [1,1,1,1,1,0],
    [1,0,0,0,0,0],
    [1,0,0,0,0,0],
    [1,0,0,0,0,0]
  ],
  'G': [
    [0,0,1,1,1,0],
    [0,1,0,0,0,0],
    [1,0,0,0,0,0],
    [1,0,0,1,1,1],
    [1,0,0,0,0,1],
    [0,1,0,0,0,1],
    [0,0,1,1,1,0]
  ],
  'H': [
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,1,1,1,1,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1]
  ],
  'I': [
    [0,1,1,1,1,0],
    [0,0,0,1,0,0],
    [0,0,0,1,0,0],
    [0,0,0,1,0,0],
    [0,0,0,1,0,0],
    [0,0,0,1,0,0],
    [0,1,1,1,1,0]
  ],
  'J': [
    [0,0,0,0,1,0],
    [0,0,0,0,1,0],
    [0,0,0,0,1,0],
    [0,0,0,0,1,0],
    [0,0,0,0,1,0],
    [1,0,0,0,1,0],
    [0,1,1,1,0,0]
  ],
  'K': [
    [1,0,0,0,0,1],
    [1,0,0,0,1,0],
    [1,0,0,1,0,0],
    [1,1,1,0,0,0],
    [1,0,0,1,0,0],
    [1,0,0,0,1,0],
    [1,0,0,0,0,1]
  ],
  'L': [
    [1,0,0,0,0,0],
    [1,0,0,0,0,0],
    [1,0,0,0,0,0],
    [1,0,0,0,0,0],
    [1,0,0,0,0,0],
    [1,0,0,0,0,0],
    [1,1,1,1,1,1]
  ],
  'M': [
    [1,0,0,0,0,1],
    [1,1,0,0,1,1],
    [1,0,1,1,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1]
  ],
  'N': [
    [1,0,0,0,0,1],
    [1,1,0,0,0,1],
    [1,0,1,0,0,1],
    [1,0,0,1,0,1],
    [1,0,0,0,1,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1]
  ],
  'O': [
    [0,0,1,1,0,0],
    [0,1,0,0,1,0],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [0,1,0,0,1,0],
    [0,0,1,1,0,0]
  ],
  'P': [
    [1,1,1,1,1,0],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,1,1,1,1,0],
    [1,0,0,0,0,0],
    [1,0,0,0,0,0],
    [1,0,0,0,0,0]
  ],
  'Q': [
    [0,0,1,1,0,0],
    [0,1,0,0,1,0],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,1,0,1],
    [0,1,0,0,1,0],
    [0,0,1,1,0,1]
  ],
  'R': [
    [1,1,1,1,1,0],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,1,1,1,1,0],
    [1,0,0,1,0,0],
    [1,0,0,0,1,0],
    [1,0,0,0,0,1]
  ],
  'S': [
    [0,0,1,1,1,1],
    [0,1,0,0,0,0],
    [1,0,0,0,0,0],
    [0,1,1,1,1,0],
    [0,0,0,0,0,1],
    [0,0,0,0,0,1],
    [1,1,1,1,1,0]
  ],
  'T': [
    [1,1,1,1,1,1],
    [0,0,0,1,0,0],
    [0,0,0,1,0,0],
    [0,0,0,1,0,0],
    [0,0,0,1,0,0],
    [0,0,0,1,0,0],
    [0,0,0,1,0,0]
  ],
  'U': [
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [0,1,1,1,1,0]
  ],
  'V': [
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [0,1,0,0,1,0],
    [0,1,0,0,1,0],
    [0,0,1,1,0,0]
  ],
  'W': [
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,0,0,0,1],
    [1,0,1,1,0,1],
    [1,1,0,0,1,1],
    [1,0,0,0,0,1]
  ],
  'X': [
    [1,0,0,0,0,1],
    [0,1,0,0,1,0],
    [0,0,1,1,0,0],
    [0,0,0,1,0,0],
    [0,0,1,1,0,0],
    [0,1,0,0,1,0],
    [1,0,0,0,0,1]
  ],
  'Y': [
    [1,0,0,0,0,1],
    [0,1,0,0,1,0],
    [0,0,1,1,0,0],
    [0,0,0,1,0,0],
    [0,0,0,1,0,0],
    [0,0,0,1,0,0],
    [0,0,0,1,0,0]
  ],
  'Z': [
    [1,1,1,1,1,1],
    [0,0,0,0,0,1],
    [0,0,0,0,1,0],
    [0,0,0,1,0,0],
    [0,0,1,0,0,0],
    [0,1,0,0,0,0],
    [1,1,1,1,1,1]
  ],
  
  // 符号
  '.': [
    [0,0],
    [0,0],
    [0,0],
    [0,0],
    [0,0],
    [1,1]
  ],
  ':': [
    [0,0],
    [1,1],
    [0,0],
    [0,0],
    [1,1],
    [0,0]
  ],
  '!': [
    [0,1,0],
    [0,1,0],
    [0,1,0],
    [0,1,0],
    [0,0,0],
    [0,1,0]
  ],
  '?': [
    [0,1,1,1,0],
    [1,0,0,0,1],
    [0,0,0,0,1],
    [0,0,0,1,0],
    [0,0,0,0,0],
    [0,0,0,1,0]
  ],
  '-': [
    [0,0,0,0],
    [0,0,0,0],
    [1,1,1,1],
    [0,0,0,0],
    [0,0,0,0]
  ],
  '_': [
    [0,0,0,0],
    [0,0,0,0],
    [0,0,0,0],
    [0,0,0,0],
    [1,1,1,1]
  ],
  ' ': [
    [0,0,0],
    [0,0,0],
    [0,0,0],
    [0,0,0],
    [0,0,0]
  ]
}

interface PixelFontOptions {
  scale?: number
  color?: string
  backgroundColor?: string
  spacing?: number
}

export class PixelFontRenderer {
  private ctx: CanvasRenderingContext2D
  private defaultOptions: PixelFontOptions = {
    scale: 2,
    color: '#ffffff',
    backgroundColor: 'transparent',
    spacing: 1
  }

  constructor(ctx: CanvasRenderingContext2D) {
    this.ctx = ctx
  }

  /**
   * 绘制像素字体文本
   */
  drawText(
    text: string, 
    x: number, 
    y: number, 
    options: PixelFontOptions = {}
  ): { width: number; height: number } {
    const opts = { ...this.defaultOptions, ...options }
    const scale = opts.scale ?? 1
    const color = opts.color ?? '#ffffff'
    const backgroundColor = opts.backgroundColor ?? 'transparent'
    const spacing = opts.spacing ?? 1
    
    const charWidth = 6 * scale  // 基础字符宽度
    const charHeight = 8 * scale // 基础字符高度
    const totalWidth = text.length * (charWidth + spacing * scale) - spacing * scale
    
    // 绘制背景（如果指定）
    if (backgroundColor !== 'transparent') {
      this.ctx.fillStyle = backgroundColor
      this.ctx.fillRect(x, y, totalWidth, charHeight)
    }

    // 绘制每个字符
    for (let i = 0; i < text.length; i++) {
      const char = text[i].toUpperCase()
      const charX = x + i * (charWidth + spacing * scale)
      
      this.drawCharacter(char, charX, y, scale, color)
    }

    return { width: totalWidth, height: charHeight }
  }

  /**
   * 绘制单个字符
   */
  private drawCharacter(
    char: string, 
    x: number, 
    y: number, 
    scale: number, 
    color: string
  ) {
    const pixelData = PIXEL_FONT_CHARS[char] || PIXEL_FONT_CHARS[' '] // 默认空格
    
    this.ctx.fillStyle = color
    
    for (let row = 0; row < pixelData.length; row++) {
      for (let col = 0; col < pixelData[row].length; col++) {
        if (pixelData[row][col] === 1) {
          this.ctx.fillRect(
            x + col * scale,
            y + row * scale,
            scale,
            scale
          )
        }
      }
    }
  }

  /**
   * 测量文本尺寸
   */
  measureText(text: string, scale: number = 2, spacing: number = 1): { width: number; height: number } {
    const charWidth = 6 * scale
    const charHeight = 8 * scale
    const totalWidth = text.length * (charWidth + spacing * scale) - spacing * scale
    
    return { width: totalWidth, height: charHeight }
  }

  /**
   * 绘制带边框的像素文本
   */
  drawTextWithBorder(
    text: string,
    x: number,
    y: number,
    options: PixelFontOptions & { borderColor?: string; borderWidth?: number } = {}
  ): { width: number; height: number } {
    const opts = { 
      borderColor: '#000000', 
      borderWidth: 1, 
      ...this.defaultOptions, 
      ...options 
    }
    
    // 先绘制边框（偏移绘制）
    const borderOffsets = [
      [-1, -1], [0, -1], [1, -1],
      [-1, 0],           [1, 0],
      [-1, 1],  [0, 1],  [1, 1]
    ]
    
    borderOffsets.forEach(([dx, dy]) => {
      this.drawText(text, x + dx * opts.borderWidth!, y + dy * opts.borderWidth!, {
        scale: opts.scale,
        color: opts.borderColor,
        spacing: opts.spacing
      })
    })
    
    // 再绘制主体文本
    return this.drawText(text, x, y, opts)
  }

  /**
   * 创建像素字体的DOM元素（用于非Canvas场景）
   */
  static createPixelTextElement(
    text: string,
    className: string = '',
    style: Partial<CSSStyleDeclaration> = {}
  ): HTMLElement {
    const container = document.createElement('div')
    container.className = `pixel-font ${className}`
    Object.assign(container.style, {
      fontFamily: 'monospace',
      fontSize: '16px',
      lineHeight: '1',
      letterSpacing: '1px',
      textTransform: 'uppercase',
      ...style
    })
    container.textContent = text
    return container
  }
}

// 预定义的字体样式
export const PIXEL_FONT_STYLES = {
  DEFAULT: { scale: 2, color: '#ffffff' },
  TITLE: { scale: 3, color: '#ffff00', spacing: 2 },
  WARNING: { scale: 2, color: '#ff0000' },
  SUCCESS: { scale: 2, color: '#00ff00' },
  INFO: { scale: 2, color: '#00ffff' },
  DIM: { scale: 1, color: '#888888' }
} as const

// CSS辅助类
export const PIXEL_FONT_CSS = `
.pixel-font {
  font-family: 'Courier New', monospace;
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: bold;
}

.pixel-font-title {
  font-size: 24px;
  color: #ffff00;
  text-shadow: 2px 2px 0px #000000;
}

.pixel-font-warning {
  color: #ff0000;
  text-shadow: 1px 1px 0px #000000;
}

.pixel-font-success {
  color: #00ff00;
  text-shadow: 1px 1px 0px #000000;
}

.pixel-font-info {
  color: #00ffff;
  text-shadow: 1px 1px 0px #000000;
}
`