#!/usr/bin/env python3
"""Run the generated GPU producer against a full queue with no consumer."""
from pathlib import Path
import subprocess, tempfile
root=Path(__file__).resolve().parents[1]
cache=Path((root/'.local/headless-cache').read_text().strip())
worker=(cache/'native-local/headless/gpu_thread.cpp').read_text()
start=worker.index('u64 ThreadManager::PushCommand(')
body=worker[start:worker.index('\n} // namespace',start)]
assert 'state.queue.EmplaceWait(' not in body
main=(root/'headless/main.cpp').read_text()
assert 'system.Pause();' not in main
code=r'''
#include <array>
#include <variant>
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <deque>
#include <future>
#include <mutex>
#include <stop_token>
#include <thread>
#include "common/bounded_threadsafe_queue.h"
using u64=unsigned long long;
struct CpuReadCommand { struct Diagnostic { unsigned before_lock{}; }* diagnostic{}; };
struct RunCommand { int id{}; };
using CommandData=std::variant<int,CpuReadCommand,RunCommand>;
namespace ReadbackDependencyDiagnostics { inline unsigned Now() { return 0; } }
namespace VideoCommon { struct GpuSplit { static GpuSplit& Get() { static GpuSplit split; return split; } void Stop() {} }; }
struct Item { CommandData command{}; u64 fence{}; bool block{}; u64 sequence{}; };
struct ThreadManager {
 struct { std::mutex write_lock; u64 last_fence{}; std::atomic<u64> signaled_fence{},published_work_sequence{}; bool shutting_down{};
          Common::SPSCQueue<Item,2> queue; std::condition_variable_any cv; std::deque<Item> overflow; } state;
 std::stop_source stop_source;
 u64 PushCommand(CommandData&&,bool,bool);
 // The worker file defines these after PushCommand; here there is no worker to end.
 void NotifyShutdown();
 void InvalidateReadbackCache() {}
 void Stop() { stop_source.request_stop(); }
 bool IsCurrentThread() const { return false; }
};
// headless/CMakeLists.txt times a push that found the queue full (gpu_queue_full), so the body
// below carries Eden's Timer. This standalone TU does not include headless/performance.h - whose
// clock is an extern the test would have to link - so the Timer is stubbed here: two atomics and
// a clock read on scope exit cannot change what the queue does.
namespace Eden::Performance {
struct Totals { std::atomic<unsigned long long> calls{}, nanoseconds{}, requested_bytes{}; };
inline Totals gpu_queue_full;
class Timer {
public:
    explicit Timer(Totals&, unsigned long long = 0) {}
};
} // namespace Eden::Performance
'''+body+r'''
int main() {
 ThreadManager manager;
 assert(manager.PushCommand(1,false,true)==1);
 assert(manager.PushCommand(2,false,true)==2);
 auto blocked=std::async(std::launch::async,[&]{return manager.PushCommand(3,false,true);});
 assert(blocked.wait_for(std::chrono::milliseconds(10))==std::future_status::timeout);
 manager.stop_source.request_stop();
 assert(blocked.wait_for(std::chrono::seconds(1))==std::future_status::ready);
 assert(blocked.get()==0);
 Item item; assert(manager.state.queue.TryPop(item)&&std::get<int>(item.command)==1);
 assert(manager.state.queue.TryPop(item)&&std::get<int>(item.command)==2);
 assert(!manager.state.queue.TryPop(item));
 assert(manager.PushCommand(4,false,true)==0);
 assert(!manager.state.queue.TryPop(item));
 ThreadManager synchronous;
 auto fence_wait=std::async(std::launch::async,[&]{return synchronous.PushCommand(5,true,false);});
 assert(fence_wait.wait_for(std::chrono::milliseconds(10))==std::future_status::timeout);
 synchronous.stop_source.request_stop();
 assert(fence_wait.wait_for(std::chrono::seconds(1))==std::future_status::ready);
 fence_wait.get();
 // A full queue: a RunCommand goes to the overflow at once (its callers hold locks the GPU thread
 // takes), and later commands wait until the overflow is empty, so the order stays.
 ThreadManager overflowing;
 assert(overflowing.PushCommand(10,false,true)==1);
 assert(overflowing.PushCommand(11,false,true)==2);
 auto run=std::async(std::launch::async,[&]{return overflowing.PushCommand(RunCommand{12},false,true);});
 assert(run.wait_for(std::chrono::seconds(1))==std::future_status::ready);
 assert(run.get()==3);
 auto waiting=std::async(std::launch::async,[&]{return overflowing.PushCommand(13,false,true);});
 assert(overflowing.state.queue.TryPop(item)&&std::get<int>(item.command)==10);
 assert(waiting.wait_for(std::chrono::milliseconds(20))==std::future_status::timeout);
 assert(overflowing.state.queue.TryPop(item)&&std::get<int>(item.command)==11);
 {
  std::scoped_lock lk{overflowing.state.write_lock};
  assert(overflowing.state.overflow.size()==1&&overflowing.state.overflow.front().fence==3);
  assert(std::get<RunCommand>(overflowing.state.overflow.front().command).id==12);
  overflowing.state.overflow.pop_front();
 }
 assert(waiting.wait_for(std::chrono::seconds(1))==std::future_status::ready);
 assert(waiting.get()==4);
 assert(overflowing.state.queue.TryPop(item)&&std::get<int>(item.command)==13&&item.fence==4);
}
'''
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp)/'check.cpp';p.write_text(code);exe=Path(tmp)/'check'
 subprocess.run(['c++','-std=c++20','-pthread','-fsanitize=address,undefined','-I'+str(cache/'source/src'),str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,timeout=10)
print('GPU producer cancellation: PASS full queue, ordered contents, stopped enqueue, fence wait and overflow')