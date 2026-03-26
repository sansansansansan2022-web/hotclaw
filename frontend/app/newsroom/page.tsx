'use client'

import NewsroomScene from '../../components/NewsroomScene'

export default function NewsroomPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      <div className="container mx-auto px-4 py-6">
        {/* 标题栏 */}
        <div className="mb-6 text-center">
          <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-blue-400 via-purple-500 to-cyan-400 bg-clip-text text-transparent">
            像素风 AI 新闻编辑部
          </h1>
          <p className="text-slate-400">基于 OpenClaw 真实像素素材 • 专业级2D场景实现</p>
        </div>
        
        {/* 主要场景区域 */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-slate-700/50 shadow-2xl mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold flex items-center">
              <span className="mr-3 text-3xl">🏢</span>
              专业像素编辑部场景
            </h2>
            <div className="flex space-x-3">
              <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-all duration-200 flex items-center text-sm">
                <span className="mr-2">🎮</span>
                2D视角
              </button>
              <button className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-all duration-200 flex items-center text-sm">
                <span className="mr-2">📸</span>
                截图
              </button>
            </div>
          </div>
          
          <NewsroomScene />
        </div>
        
        {/* 说明面板 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-5 border border-slate-700/50 shadow-xl">
            <h3 className="text-lg font-bold mb-3 flex items-center">
              <span className="mr-2 text-xl">🎨</span>
              像素艺术特色
            </h3>
            <ul className="text-sm space-y-2 text-slate-300">
              <li>• 21帧精灵图动画系统</li>
              <li>• 4层垂直场景结构</li>
              <li>• 手绘像素风格砖墙</li>
              <li>• 精确的工位布局设计</li>
            </ul>
          </div>
          
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-5 border border-slate-700/50 shadow-xl">
            <h3 className="text-lg font-bold mb-3 flex items-center">
              <span className="mr-2 text-xl">🤖</span>
              6智能体系统
            </h3>
            <ul className="text-sm space-y-2 text-slate-300">
              <li>• 飞书写作助手 (working)</li>
              <li>• Discord编辑专家 (sync)</li>
              <li>• QQ校对大师 (idle)</li>
              <li>• 微信设计专员 (working)</li>
              <li>• Telegram调研师 (offline)</li>
              <li>• Github开发者 (sync)</li>
            </ul>
          </div>
          
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-5 border border-slate-700/50 shadow-xl">
            <h3 className="text-lg font-bold mb-3 flex items-center">
              <span className="mr-2 text-xl">⚡</span>
              智能行为
            </h3>
            <ul className="text-sm space-y-2 text-slate-300">
              <li>• working: 坐在工位专注工作</li>
              <li>• idle: 偶尔去茶水间休息</li>
              <li>• sync: 在工位间传递信息</li>
              <li>• offline: 透明显示，暂停活动</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}