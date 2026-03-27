import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  reportMarkdown: string | null;
}

export function ReportViewer({ reportMarkdown }: Props) {
  const [copied, setCopied] = useState(false);

  const stats = useMemo(() => {
    if (!reportMarkdown) return null;
    const wordCount = reportMarkdown.replace(/[#>*`-]/g, " ").split(/\s+/).filter(Boolean).length;
    const sectionCount = reportMarkdown.match(/^##\s+/gm)?.length ?? 0;
    const headingMatch = reportMarkdown.match(/^#\s+(.*)/m);
    const title = headingMatch ? headingMatch[1] : "求职研究报告";
    const focusSections = Array.from(
      reportMarkdown.matchAll(/^##\s+(.*)$/gm),
      (match) => match[1]
    ).slice(0, 6);

    return { wordCount, sectionCount, title, focusSections };
  }, [reportMarkdown]);

  const handleCopy = async () => {
    if (!reportMarkdown) return;
    try {
      await navigator.clipboard.writeText(reportMarkdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const handleDownload = () => {
    if (!reportMarkdown) return;
    const blob = new Blob([reportMarkdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${stats?.title || "report"}_${new Date().toISOString().split("T")[0]}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (!reportMarkdown) {
    return (
      <div className="h-full flex items-center justify-center text-slate-400">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-slate-100 flex items-center justify-center">
            <svg
              className="w-8 h-8 text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
          <p className="text-slate-600">暂无报告内容</p>
          <p className="text-sm text-slate-400 mt-1">完成求职研究后将在此显示结构化报告</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Report Header */}
      <div className="border-b border-slate-200 bg-gradient-to-r from-sky-50 to-emerald-50 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-slate-900 mb-2">{stats?.title}</h1>
              <p className="text-sm text-slate-600">生成时间: {new Date().toLocaleString("zh-CN")}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCopy}
                className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors flex items-center gap-2"
              >
                {copied ? (
                  <>
                    <svg className="w-4 h-4 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                    已复制
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                      />
                    </svg>
                    复制
                  </>
                )}
              </button>
              <button
                onClick={handleDownload}
                className="px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-sky-600 to-emerald-600 rounded-lg hover:from-sky-700 hover:to-emerald-700 transition-all flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                  />
                </svg>
                下载
              </button>
            </div>
          </div>
          {stats && (
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white/60 rounded-lg p-3 border border-slate-200">
                <div className="text-xs text-slate-600 mb-1">字数统计</div>
                <div className="text-lg font-semibold text-slate-900">
                  {stats.wordCount.toLocaleString()}
                </div>
              </div>
              <div className="bg-white/60 rounded-lg p-3 border border-slate-200">
                <div className="text-xs text-slate-600 mb-1">章节数量</div>
                <div className="text-lg font-semibold text-slate-900">{stats.sectionCount}</div>
              </div>
              <div className="bg-white/60 rounded-lg p-3 border border-slate-200">
                <div className="text-xs text-slate-600 mb-1">报告类型</div>
                <div className="text-lg font-semibold text-slate-900">求职行动版</div>
              </div>
            </div>
          )}
          {stats && stats.focusSections.length > 0 && (
            <div className="mt-5">
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                重点章节
              </div>
              <div className="flex flex-wrap gap-2">
                {stats.focusSections.map((section) => (
                  <span
                    key={section}
                    className="rounded-full border border-sky-200 bg-white/80 px-3 py-1 text-xs text-slate-700"
                  >
                    {section}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Report Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <article className="max-w-4xl mx-auto prose prose-slate prose-headings:font-bold prose-headings:text-slate-900 prose-p:text-slate-700 prose-a:text-blue-600 prose-strong:text-slate-900 prose-code:text-slate-800 prose-code:bg-slate-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-pre:bg-slate-900 prose-pre:text-slate-100">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{reportMarkdown}</ReactMarkdown>
        </article>
      </div>
    </div>
  );
}

