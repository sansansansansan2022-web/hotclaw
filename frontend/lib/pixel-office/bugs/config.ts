// Bug系统类型定义（简化版）
export interface BugConfig {
  enabled: boolean
  spawnRate: number
  maxBugs: number
}

export interface BugEntity {
  id: string
  x: number
  y: number
  vx: number
  vy: number
  size: number
  color: string
}

export const DEFAULT_BUG_CONFIG: BugConfig = {
  enabled: false,
  spawnRate: 0.1,
  maxBugs: 10
}