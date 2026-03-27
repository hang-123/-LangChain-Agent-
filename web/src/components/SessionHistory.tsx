import { useMemo } from "react";

interface Props {
  sessionId: string | null;
}

export function SessionHistory({ sessionId }: Props) {
  const recentQueries = useMemo(() => {
    return [];
  }, []);

  return (
    <div>
      <h3 className="font-semibold text-slate-900 mb-3 text-sm">会话信息</h3>
      {sessionId ? (
        <div className="space-y-2">
          <div className="text-xs text-slate-500 mb-2">会话ID</div>
          <div className="px-3 py-2 bg-slate-50 rounded-lg border border-slate-200">
            <code className="text-xs text-slate-700 break-all">{sessionId}</code>
          </div>
          <div className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs leading-5 text-sky-800">
            当前 memory 模式：本地持久化。会话消息会按 <code>session_id</code> 保存到本地文件，并在后续提问时做轻量相关性召回。
          </div>
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
            继续使用这个 <code>session_id</code> 再次提问时，后端不会直接塞入全部历史，而是优先召回与当前问题更相关的历史片段。
          </div>
        </div>
      ) : (
        <div className="text-sm text-slate-500">暂无活跃会话</div>
      )}

      {recentQueries.length > 0 && (
        <div className="mt-4">
          <h4 className="font-medium text-slate-900 mb-2 text-xs">历史查询</h4>
          <div className="space-y-1">
            {recentQueries.map((query, idx) => (
              <div
                key={idx}
                className="px-3 py-2 text-xs text-slate-600 bg-slate-50 rounded-lg hover:bg-slate-100 cursor-pointer transition-colors"
              >
                {query}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
