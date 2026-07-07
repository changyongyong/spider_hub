export function countByStatus(jobs) {
  return jobs.reduce(
    (result, job) => {
      result[job.status] = (result[job.status] || 0) + 1;
      return result;
    },
    { queued: 0, running: 0, done: 0, failed: 0 }
  );
}

export function workerStatus(worker) {
  if (worker.last_error || worker.stats?.last_error) {
    return { text: "异常", tone: "danger" };
  }
  if (worker.stats?.busy) {
    return { text: "忙碌", tone: "warn" };
  }
  if (worker.running) {
    return { text: "运行中", tone: "ok" };
  }
  return { text: "停止", tone: "muted" };
}

export function jobStatus(job) {
  const toneMap = {
    done: "ok",
    failed: "danger",
    running: "warn",
    queued: "muted"
  };
  return { text: job.status, tone: toneMap[job.status] || "muted" };
}

export function shortResult(job) {
  if (job.error) {
    return job.error;
  }
  if (!job.result) {
    return "-";
  }
  return JSON.stringify({
    title: job.result.title,
    status: job.result.status,
    final_url: job.result.final_url
  });
}

export function formatDate(value) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString();
}
