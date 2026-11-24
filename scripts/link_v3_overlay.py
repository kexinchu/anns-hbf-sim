"""Opt-in aggregate payload budget, keeping v2 default byte-for-byte."""
edit('include/hbf_eventlab/architecture/execution_configuration.hpp','struct UcieExecutionConfiguration {','enum class LinkAccounting { ServiceV2, PayloadV3 };\nstruct UcieExecutionConfiguration {\n    LinkAccounting accounting=LinkAccounting::ServiceV2;\n    Tick transfer(std::uint64_t payload,std::uint64_t control) const;')
edit('src/architecture/execution_configuration.cpp','void ExecutionConfiguration::validate(const StaticDeviceDescription& d) const {','void ExecutionConfiguration::validate(const StaticDeviceDescription& d) const {\n    if(ucie.accounting!=LinkAccounting::ServiceV2 && ucie.accounting!=LinkAccounting::PayloadV3)throw std::invalid_argument("unknown link accounting");')
edit('src/architecture/execution_configuration.cpp','ucie.serialization(checked_add(ucie.overhead.request_control_bytes,largest_write))','ucie.transfer(largest_write,ucie.overhead.request_control_bytes)')
edit('src/architecture/execution_configuration.cpp','ucie.serialization(checked_add(ucie.overhead.response_control_bytes,host_unit_bytes))','ucie.transfer(host_unit_bytes,ucie.overhead.response_control_bytes)')
edit('src/architecture/execution_configuration.cpp','Tick UcieExecutionConfiguration::serialization', '''Tick UcieExecutionConfiguration::transfer(std::uint64_t payload,std::uint64_t control) const {
    if(accounting==LinkAccounting::ServiceV2)return serialization(checked_add(payload,control));
    if(accounting!=LinkAccounting::PayloadV3)throw std::invalid_argument("unknown link accounting");
    if(payload)return serialization(payload); // Effective payload budget includes amortized overhead.
    // Control-only path: explicit assumed service amount at raw x64 line rate.
    const auto rate=std::uint64_t(ucie_speed_profile(speed_grade).gt_per_second)*8;
    const auto ps=checked_mul(control,1000);return Tick{ps/rate+(ps%rate!=0)};
}
Tick UcieExecutionConfiguration::serialization''')
edit('src/runtime/device_driver.cpp','config_.ucie.serialization(service)','config_.ucie.transfer(payload,config_.ucie.overhead.request_control_bytes)')
edit('src/runtime/device_driver.cpp','config_.ucie.serialization(chosen->service_bytes)','config_.ucie.transfer(chosen->service_bytes-config_.ucie.overhead.response_control_bytes,config_.ucie.overhead.response_control_bytes)')
edit('src/configuration/simulation_configuration.cpp','template<class T> void parse(const std::string& s,std::optional<T>& value)','''void parse(const std::string& s,LinkAccounting& value) {
    if(s=="service-v2")value=LinkAccounting::ServiceV2;
    else if(s=="payload-v3")value=LinkAccounting::PayloadV3;
    else throw std::invalid_argument("expected service-v2 or payload-v3");
}
template<class T> void parse(const std::string& s,std::optional<T>& value)''')
edit('src/configuration/simulation_configuration.cpp','std::string format(UcieSpeedGrade value)', 'std::string format(LinkAccounting value) {return value==LinkAccounting::ServiceV2?"service-v2":"payload-v3";}\nstd::string format(UcieSpeedGrade value)')
edit('src/configuration/simulation_configuration.cpp','    add("execution.ucie.request_control_bytes",e.ucie.overhead.request_control_bytes);','    add("execution.ucie.accounting",e.ucie.accounting);\n    add("execution.ucie.request_control_bytes",e.ucie.overhead.request_control_bytes);')
# Nonempty transfers no longer exercise control-only serialization in v3.
# Validate the control path separately, including fixed-latency overflow.
edit('src/architecture/execution_configuration.cpp','        const auto request=ucie.transfer(largest_write,ucie.overhead.request_control_bytes);', '''        (void)checked_add(ucie.transfer(0,ucie.overhead.request_control_bytes).value,ucie.overhead.request_fixed_latency.value);
        (void)checked_add(ucie.transfer(0,ucie.overhead.response_control_bytes).value,ucie.overhead.response_fixed_latency.value);
        const auto request=ucie.transfer(largest_write,ucie.overhead.request_control_bytes);''')
