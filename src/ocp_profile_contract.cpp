// Narrow configuration contract, NOT OCP certification or timing calibration.
#include "hbf_eventlab/configuration/simulation_configuration.hpp"
#include <iostream>
#include <sstream>
#include <stdexcept>
using namespace hbf_eventlab;
void require(bool b) { if (!b) throw std::runtime_error("profile contract failed"); }
template<class F> void reject(F f) {
  bool rejected=false; try { f(); } catch(const std::exception&) { rejected=true; }
  require(rejected);
}
int main() { try {
  // OCP v0.7 §5.3.1, §5.4.1: distinct command and logical-page units.
  require(host_unit_bytes==64 && dlu_bytes==4096);
  // §5.9.2.1: allowed *decoded* capabilities, not raw register encodings.
  for (unsigned n: {1u,256u,512u,1024u,2048u,4096u,8192u,16384u}) {
    SimulationConfiguration c; c.device.capabilities.mocs_supported=n;
    c.device.selected.mocs_selected=n; (void)resolve_configuration(c);
  }
  for (unsigned n: {0u,2u,64u,128u,255u,257u,32768u}) {
    SimulationConfiguration c; c.device.capabilities.mocs_supported=n;
    c.device.selected.mocs_selected=n; reject([&]{ (void)resolve_configuration(c); });
  }
  SimulationConfiguration over; over.device.selected.mocs_selected=512;
  reject([&]{ (void)resolve_configuration(over); });
  // Interface guards: unsupported profiles/options must fail, not silently approximate.
  SimulationConfiguration wrong; wrong.device.spec_profile="unverified";
  reject([&]{ (void)resolve_configuration(wrong); });
  reject([&]{ apply_configuration_override(wrong,"execution.core_bandwidth","100"); });
  auto resolved=resolve_configuration({}); std::ostringstream ini;
  write_effective_configuration(ini,resolved); std::istringstream input(ini.str());
  auto restored=resolve_configuration(read_configuration(input,"roundtrip"));
  require(restored.values().device.selected.mocs_selected==256);
  std::cout << "{\"status\":\"PASS\",\"scope\":\"OCP_CONFIGURATION_SUBSET_ONLY\",\"legal_mocs_cases\":8,\"reserved_mocs_cases\":7,\"performance_ready\":false}\n";
} catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; return 1; } }
