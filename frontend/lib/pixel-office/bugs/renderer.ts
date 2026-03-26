import type { BugEntity } from './types'

export function renderBugs(
  ctx: CanvasRenderingContext2D,
  bugs: BugEntity[],
  offsetX: number,
  offsetY: number,
  zoom: number
): void {
  bugs.forEach(bug => {
    ctx.save()
    ctx.fillStyle = bug.color
    ctx.beginPath()
    ctx.arc(
      offsetX + bug.x * zoom,
      offsetY + bug.y * zoom,
      bug.size * zoom,
      0,
      Math.PI * 2
    )
    ctx.fill()
    ctx.restore()
  })
}