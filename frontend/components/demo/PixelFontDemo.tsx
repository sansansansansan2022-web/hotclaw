/** Pixel Font Demo Component - 像素字体系统演示
 *
 * 展示自定义像素字体的各种用法和样式
 */

import { useEffect, useRef } from 'react'
import { PixelFontRenderer, PIXEL_FONT_STYLES } from '@/lib/pixel-font/PixelFontSystem'

export default function PixelFontDemo() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // 设置canvas大小
    canvas.width = 800
    canvas.height = 600
    ctx.imageSmoothingEnabled = false

    // 创建字体渲染器
    const fontRenderer = new PixelFontRenderer(ctx)

    // 清空画布
    ctx.fillStyle = '#1a1a2e'
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    // 绘制各种样式的文本
    let yPos = 30

    // 标题样式
    fontRenderer.drawText('HOTCLAW EDITORIAL SYSTEM', 20, yPos, {
      ...PIXEL_FONT_STYLES.TITLE,
      color: '#ffff00'
    })
    yPos += 40

    // 默认样式信息
    fontRenderer.drawText('SYSTEM STATUS: ONLINE', 20, yPos, PIXEL_FONT_STYLES.DEFAULT)
    yPos += 30

    // 成功信息
    fontRenderer.drawText('✓ ALL AGENTS ACTIVE', 20, yPos, PIXEL_FONT_STYLES.SUCCESS)
    yPos += 25

    // 警告信息
    fontRenderer.drawText('! HIGH CPU USAGE DETECTED', 20, yPos, PIXEL_FONT_STYLES.WARNING)
    yPos += 25

    // 信息提示
    fontRenderer.drawText('> PROCESSING TASK #12345', 20, yPos, PIXEL_FONT_STYLES.INFO)
    yPos += 35

    // Agent状态列表
    const agents = ['小档', '小热', '小策', '小标', '小文', '小审']
    agents.forEach((agent, index) => {
      const status = index % 3 === 0 ? 'WORKING' : index % 3 === 1 ? 'IDLE' : 'ERROR'
      const style = index % 3 === 0 ? PIXEL_FONT_STYLES.INFO : 
                   index % 3 === 1 ? PIXEL_FONT_STYLES.DEFAULT : 
                   PIXEL_FONT_STYLES.WARNING
      
      fontRenderer.drawText(`${agent}: ${status}`, 20, yPos + index * 25, style)
    })

    // 绘制带边框的标题
    yPos += 180
    fontRenderer.drawTextWithBorder('AGENT PERFORMANCE METRICS', 20, yPos, {
      ...PIXEL_FONT_STYLES.TITLE,
      color: '#00ff00',
      borderColor: '#000000',
      borderWidth: 2
    })

    // 数值显示
    yPos += 50
    fontRenderer.drawText('SUCCESS RATE: 98.5%', 20, yPos, PIXEL_FONT_STYLES.DEFAULT)
    yPos += 25
    fontRenderer.drawText('AVG RESPONSE: 2.3S', 20, yPos, PIXEL_FONT_STYLES.DEFAULT)
    yPos += 25
    fontRenderer.drawText('TASKS COMPLETED: 127', 20, yPos, PIXEL_FONT_STYLES.DEFAULT)

    // 装饰性元素
    ctx.fillStyle = '#4a4a8a'
    for (let i = 0; i < 20; i++) {
      ctx.fillRect(20 + i * 20, yPos + 30, 10, 2)
    }

  }, [])

  return (
    <div className="p-6 bg-gray-900 min-h-screen">
      <h1 className="text-2xl font-mono text-yellow-400 mb-6">Pixel Font System Demo</h1>
      
      <div className="bg-black rounded-lg p-4 inline-block">
        <canvas 
          ref={canvasRef} 
          className="border border-gray-700"
          style={{ imageRendering: 'pixelated' }}
        />
      </div>

      <div className="mt-6 grid grid-cols-2 gap-4 max-w-2xl">
        <div className="bg-gray-800 p-4 rounded">
          <h2 className="text-green-400 font-mono text-sm mb-2">Features:</h2>
          <ul className="text-gray-300 text-xs font-mono space-y-1">
            <li>• Custom 8x8 pixel font</li>
            <li>• Multiple color schemes</li>
            <li>• Scalable rendering</li>
            <li>• Border effects</li>
            <li>• Canvas integration</li>
          </ul>
        </div>

        <div className="bg-gray-800 p-4 rounded">
          <h2 className="text-cyan-400 font-mono text-sm mb-2">Styles:</h2>
          <div className="space-y-2 text-xs font-mono">
            <div className="text-yellow-400">TITLE: Large & Bright</div>
            <div className="text-green-400">SUCCESS: Green status</div>
            <div className="text-red-400">WARNING: Red alerts</div>
            <div className="text-cyan-400">INFO: Blue information</div>
            <div className="text-gray-500">DIM: Gray secondary</div>
          </div>
        </div>
      </div>

      <div className="mt-6 bg-gray-800 p-4 rounded max-w-2xl">
        <h2 className="text-purple-400 font-mono text-sm mb-3">Usage Examples:</h2>
        <pre className="text-gray-300 text-xs font-mono whitespace-pre-wrap">
{`// Basic usage
const renderer = new PixelFontRenderer(ctx);
renderer.drawText('HELLO WORLD', 10, 10, {
  scale: 2,
  color: '#ffffff'
});

// With border effect
renderer.drawTextWithBorder('TITLE', 10, 30, {
  ...PIXEL_FONT_STYLES.TITLE,
  borderColor: '#000000',
  borderWidth: 1
});`}
        </pre>
      </div>
    </div>
  )
}