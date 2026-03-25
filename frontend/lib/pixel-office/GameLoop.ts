/** PixelOffice game loop — requestAnimationFrame-based update/render loop.
 *
 * Pattern: update(dt) → render() → requestAnimationFrame
 */

import { OfficeState } from './OfficeState'
import { OptimizedRenderer } from './OptimizedRenderer' // 使用优化版本
import type { NodeState } from '@/hooks/useTaskSSE'

export class GameLoop {
  private canvas: HTMLCanvasElement
  private state: OfficeState
  private renderer: OptimizedRenderer
  private rafId = 0
  private lastTime = 0
  private stopped = false

  // For tracking task state
  private activeNodeAgentId: string | null = null

  constructor(canvas: HTMLCanvasElement, state: OfficeState, zoom = 2) {
    this.canvas = canvas
    this.state = state
    this.renderer = new OptimizedRenderer(canvas, zoom) // 使用优化渲染器
  }

  start() {
    this.lastTime = 0
    this.stopped = false
    const frame = (time: number) => {
      if (this.stopped) return
      const dt = this.lastTime === 0 ? 0 : Math.min((time - this.lastTime) / 1000, 0.1)
      this.lastTime = time

      this.state.update(dt)
      this.renderer.render(this.state)

      this.rafId = requestAnimationFrame(frame)
    }
    this.rafId = requestAnimationFrame(frame)
  }

  stop() {
    this.stopped = true
    cancelAnimationFrame(this.rafId)
  }

  setZoom(zoom: number) {
    this.renderer.setZoom(zoom)
  }

  // ── SSE event integration ─────────────────────────────────

  /** Called when a node starts executing */
  onNodeStart(node: NodeState) {
    this.state.onNodeStart(node.agent_id, node.name)
  }

  /** Called when a node completes */
  onNodeComplete(node: NodeState) {
    this.state.onNodeComplete(
      node.agent_id,
      node.name,
      node.output_summary,
      node.elapsed_seconds ?? 0,
    )
  }

  /** Called when a node fails */
  onNodeError(node: NodeState) {
    this.state.onNodeError(node.agent_id, node.error ?? 'Error')
  }

  /** Called when task completes — reset all agents to idle */
  onTaskComplete() {
    for (const ch of this.state.getAllCharacters()) {
      ch.isActive = false
      ch.state = 'idle'
      ch.currentTool = null
      ch.bubbleText = '✓ 完成!'
      ch.bubbleTimer = 4.0
      ch.bubbleType = 'output'
    }
  }

  /** Called when task errors — show error on active agent */
  onTaskError(message: string) {
    // Find active agent
    for (const ch of this.state.getAllCharacters()) {
      if (ch.isActive) {
        ch.bubbleText = `✗ ${message.slice(0, 12)}`
        ch.bubbleTimer = 6.0
        ch.bubbleType = 'error'
        break
      }
    }
  }

  // ── Selection ─────────────────────────────────────────────

  selectAgent(id: number | null) {
    this.state.selectAgent(id)
  }

  getCharacterAt(worldX: number, worldY: number): number | null {
    const canvasRect = this.canvas.getBoundingClientRect()
    const scaleX = this.canvas.width / canvasRect.width
    const scaleY = this.canvas.height / canvasRect.height

    // Convert screen coords to canvas coords
    const canvasX = (worldX - canvasRect.left) * scaleX
    const canvasY = (worldY - canvasRect.top) * scaleY

    // Compute offset (same as renderer)
    const { layout } = this.state
    const { zoom } = this.renderer as unknown as { zoom: number }
    const TILE_SIZE = 16
    const mapW = layout.cols * TILE_SIZE * zoom
    const mapH = layout.rows * TILE_SIZE * zoom
    const offsetX = Math.floor((this.canvas.width - mapW) / 2)
    const offsetY = Math.floor((this.canvas.height - mapH) / 2)

    // Convert to world pixels
    const worldPx = (canvasX - offsetX) / zoom
    const worldPy = (canvasY - offsetY) / zoom

    // Hit test each character
    const CHAR_W = 16
    const CHAR_H = 24
    const HALF_W = CHAR_W / 2
    for (const ch of this.state.getAllCharacters()) {
      const left = ch.x - HALF_W
      const right = ch.x + HALF_W
      const top = ch.y - CHAR_H
      const bottom = ch.y
      if (worldPx >= left && worldPx <= right && worldPy >= top && worldPy <= bottom) {
        return ch.id
      }
    }
    return null
  }
}
