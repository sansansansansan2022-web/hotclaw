// Bug系统简化实现
import type { BugEntity } from './types'
import type { BugConfig } from './config'

export class BugSystem {
  private bugs: BugEntity[] = []
  private config: BugConfig
  
  constructor(config: BugConfig) {
    this.config = config
  }
  
  update(dt: number) {
    // 简化的bug更新逻辑
    if (this.config.enabled && Math.random() < this.config.spawnRate * dt) {
      this.spawnBug()
    }
    
    // 更新现有bugs
    this.bugs = this.bugs.filter(bug => {
      bug.x += bug.vx * dt
      bug.y += bug.vy * dt
      return bug.x >= 0 && bug.x <= 1000 && bug.y >= 0 && bug.y <= 1000
    })
  }
  
  private spawnBug() {
    if (this.bugs.length >= this.config.maxBugs) return
    
    const bug: BugEntity = {
      id: `bug-${Date.now()}`,
      x: Math.random() * 800,
      y: Math.random() * 600,
      vx: (Math.random() - 0.5) * 50,
      vy: (Math.random() - 0.5) * 50,
      size: Math.random() * 3 + 1,
      color: '#' + Math.floor(Math.random()*16777215).toString(16)
    }
    
    this.bugs.push(bug)
  }
  
  getBugs(): BugEntity[] {
    return this.bugs
  }
}