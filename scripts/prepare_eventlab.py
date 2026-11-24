"""Materialize a reviewable overlay. Never edit pinned vendor. Fail on changed anchors."""
import pathlib,shutil,sys
src,dst=map(pathlib.Path,sys.argv[1:3]);shutil.copytree(src,dst,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.git'))
def edit(name,old,new):
 p=dst/name;s=p.read_text()
 if s.count(old)!=1:raise RuntimeError(f'patch anchor changed: {name}: {old}')
 p.write_text(s.replace(old,new))
edit('include/hbf_eventlab/architecture/execution_configuration.hpp',
 'struct ExecutionConfiguration {',
 '''struct ExecutionConfiguration {
    // Research overlay: 0 keeps donor ideal channel. Not OCP-mandated timings.
    std::uint64_t core_bytes_per_ns=0;
    Tick core_propagation{0};
    std::function<void(ChannelId,std::uint32_t,Tick,Tick,Tick)> core_observer;''')
edit('include/hbf_eventlab/runtime/device_driver.hpp','    EventId schedule(Tick,EventPhase,std::function<void()>);',
 '''    std::map<std::pair<ChannelId,std::uint32_t>,Tick> core_available_;
    Tick core_transfer(BankKey bank) {
        if(!config_.core_bytes_per_ns) return events_.now();
        auto& available=core_available_[{bank.channel,topology_.core_channel(bank.die)}];
        const auto start=std::max(available.value,events_.now().value);
        const auto numerator=checked_mul(dlu_bytes,1000);
        const auto duration=numerator/config_.core_bytes_per_ns+(numerator%config_.core_bytes_per_ns!=0);
        available=Tick{checked_add(start,duration)};
        if(config_.core_observer) config_.core_observer(bank.channel,topology_.core_channel(bank.die),events_.now(),Tick{start},available);
        return Tick{checked_add(available.value,config_.core_propagation.value)};
    }
    EventId schedule(Tick,EventPhase,std::function<void()>);''')
edit('src/runtime/device_driver.cpp',
 'schedule(after(events_.now(),config_.media_timing.program),EventPhase::Completion,',
 'schedule(after(core_transfer(bank),config_.media_timing.program),EventPhase::Completion,')
edit('src/runtime/device_driver.cpp',
 '''                cache_.finish_fill(fill); reads_.finish_read(op.id);''',
 '''                // Separate media completion from buffer-ready/bank-release completion.
                emit("sense-media-finish",bank.channel,ticket,op.physical);
                // Reserve bus at sense completion, not at a future guessed arrival.
                schedule(core_transfer(bank),EventPhase::Completion,[this,op,fill,bank,ticket] {
                cache_.finish_fill(fill); reads_.finish_read(op.id);''')
edit('src/runtime/device_driver.cpp',
 '''                emit("sense-finish",bank.channel,ticket,op.physical); request_pump(bank.channel);
            });''',
 '''                emit("sense-finish",bank.channel,ticket,op.physical); request_pump(bank.channel);
                });
            });''')

edit('src/configuration/simulation_configuration.cpp',
 '    add("execution.media_timing.sense_ps",e.media_timing.sense);',
 '    add("execution.core_bytes_per_ns",e.core_bytes_per_ns);add("execution.core_propagation_ps",e.core_propagation);\n    add("execution.media_timing.sense_ps",e.media_timing.sense);')
edit('src/configuration/simulation_configuration.cpp',
 'Core Channel = ideal', 'Core Channel = overlay (0 rate: ideal; positive rate: finite shared half-duplex)')

edit('include/hbf_eventlab/architecture/execution_configuration.hpp', '#include <string>', '#include <string>\n#include <functional>')

# Checked reset integration in the full donor driver/host path.
exec(compile((pathlib.Path(__file__).parent/'driver_reset_overlay.py').read_text(),
             str(pathlib.Path(__file__).parent/'driver_reset_overlay.py'),'exec'))
exec(compile((pathlib.Path(__file__).parent/'external_reset_overlay.py').read_text(),
             str(pathlib.Path(__file__).parent/'external_reset_overlay.py'),'exec'))

if len(sys.argv)>3 and sys.argv[3] != 'OFF':
 exec(compile((pathlib.Path(__file__).parent/'fcfs_index_overlay.py').read_text(),
              str(pathlib.Path(__file__).parent/'fcfs_index_overlay.py'),'exec'))
exec(compile((pathlib.Path(__file__).parent/'cache_policy_overlay.py').read_text(),
             str(pathlib.Path(__file__).parent/'cache_policy_overlay.py'),'exec'))

if len(sys.argv)<5 or sys.argv[4] != 'OFF':
 exec(compile((pathlib.Path(__file__).parent/'device_index_overlay.py').read_text(),
              str(pathlib.Path(__file__).parent/'device_index_overlay.py'),'exec'))
