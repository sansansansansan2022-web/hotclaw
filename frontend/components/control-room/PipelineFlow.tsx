"use client";

import { type NodeStatus } from "@/types";

interface PipelineNode {
  node_id: string;
  name: string;
  status: NodeStatus;
  icon: string;
}

interface PipelineFlowProps {
  nodes: PipelineNode[];
}

export default function PipelineFlow({ nodes }: PipelineFlowProps) {
  return (
    <div className="cr-pipeline">
      {nodes.map((node, i) => {
        const isLast = i === nodes.length - 1;

        return (
          <div key={node.node_id} style={{ display: "flex", alignItems: "center", flex: 1, minWidth: 0 }}>
            <div className="cr-pipeline-node">
              <div className={`cr-pipeline-dot ${node.status}`}>
                {node.icon}
                {node.status === "running" && (
                  <span
                    style={{
                      position: "absolute",
                      inset: -2,
                      borderRadius: "50%",
                      border: "2px solid var(--cr-green)",
                      borderTopColor: "transparent",
                      animation: "cr-spin 1s linear infinite",
                    }}
                  />
                )}
              </div>
              <span
                style={{
                  fontSize: 10,
                  color: "var(--cr-text-muted)",
                  fontFamily: "var(--cr-font-mono)",
                  whiteSpace: "nowrap",
                  maxWidth: 65,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {node.name}
              </span>
            </div>

            {!isLast && (
              <div className="cr-pipeline-line">
                {(node.status === "completed" || node.status === "failed" || node.status === "running") && (
                  <div className={`cr-pipeline-line-fill ${node.status}`} />
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
