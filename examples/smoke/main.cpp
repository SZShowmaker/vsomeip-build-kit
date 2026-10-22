#include <vsomeip/vsomeip.hpp>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {
constexpr vsomeip::service_t service = 0x6b10;
constexpr vsomeip::instance_t instance = 1;
constexpr vsomeip::method_t method = 0x0101;
constexpr vsomeip::event_t event = 0x8001;
constexpr vsomeip::eventgroup_t group = 1;
std::vector<vsomeip::byte_t> encode(std::uint32_t seq, std::size_t size) {
    std::vector<vsomeip::byte_t> b(size);
    b[0] = 'V'; b[1] = 'S'; b[2] = 'K'; b[3] = 1;
    for (unsigned i = 0; i < 4; ++i) b[4+i] = static_cast<std::uint8_t>(seq >> (24-8*i));
    for (std::size_t i = 8; i < size; ++i) b[i] = static_cast<std::uint8_t>((seq+i) % 251);
    return b;
}
bool decode(const std::shared_ptr<vsomeip::payload>& p, std::size_t size, std::uint32_t& seq) {
    if (!p || p->get_length() != size) return false;
    const auto* b = p->get_data();
    if (b[0] != 'V' || b[1] != 'S' || b[2] != 'K' || b[3] != 1) return false;
    seq = 0;
    for (unsigned i = 0; i < 4; ++i) seq = (seq << 8) | b[4+i];
    for (std::size_t i = 8; i < size; ++i)
        if (b[i] != static_cast<std::uint8_t>((seq+i) % 251)) return false;
    return true;
}
}

int main(int argc, char** argv) {
    if (argc < 2 || std::string(argv[1]) == "--help") {
        std::cout << "someip_smoke provider|consumer [udp|tcp] [seconds=12] [payload_bytes=128]\n"
                  << "Set VSOMEIP_CONFIGURATION and VSOMEIP_APPLICATION_NAME explicitly.\n";
        return argc < 2 ? 2 : 0;
    }
    try {
        const std::string role = argv[1];
        const std::string transport = argc > 2 ? argv[2] : "udp";
        const int seconds = argc > 3 ? std::stoi(argv[3]) : 12;
        const int bytes = argc > 4 ? std::stoi(argv[4]) : 128;
        if ((role != "provider" && role != "consumer") || (transport != "udp" && transport != "tcp")
            || seconds < 2 || seconds > 3600 || bytes < 8 || bytes > (transport == "udp" ? 1200 : 65536))
            throw std::runtime_error("invalid arguments; UDP payload 8..1200, TCP 8..65536, seconds 2..3600");
        const bool provider = role == "provider";
        const bool reliable = transport == "tcp";
        const auto reliability = reliable ? vsomeip::reliability_type_e::RT_RELIABLE : vsomeip::reliability_type_e::RT_UNRELIABLE;
        const auto runtime = vsomeip::runtime::get();
        const auto app = runtime->create_application();
        if (!app->init()) throw std::runtime_error("vSomeIP init failed");
        std::atomic<bool> registered{false}, available{false};
        std::atomic<unsigned> requests{0}, responses{0}, events{0}, errors{0}, discoveries{0}, losses{0};
        std::atomic<std::uint32_t> last_event{0};
        app->register_state_handler([&](vsomeip::state_type_e state) {
            registered = state == vsomeip::state_type_e::ST_REGISTERED;
            if (!registered) return;
            if (provider) app->offer_service(service, instance, 1, 0);
            else app->request_service(service, instance, 1, 0);
        });
        app->register_message_handler(service, instance, vsomeip::ANY_METHOD,
            [&](const std::shared_ptr<vsomeip::message>& msg) {
                std::uint32_t seq = 0;
                if (!decode(msg->get_payload(), static_cast<std::size_t>(bytes), seq)) { ++errors; return; }
                if (provider && msg->get_method() == method && msg->get_message_type() == vsomeip::message_type_e::MT_REQUEST) {
                    ++requests;
                    auto reply = runtime->create_response(msg);
                    reply->set_payload(msg->get_payload());
                    app->send(reply);
                } else if (!provider && msg->get_method() == method && msg->get_message_type() == vsomeip::message_type_e::MT_RESPONSE) {
                    if (msg->get_return_code() != vsomeip::return_code_e::E_OK) ++errors;
                    else ++responses;
                } else if (!provider && msg->get_method() == event && msg->get_message_type() == vsomeip::message_type_e::MT_NOTIFICATION) {
                    last_event = seq;
                    ++events;
                } else ++errors;
            });
        if (provider) {
            app->offer_event(service, instance, event, {group}, vsomeip::event_type_e::ET_EVENT,
                             std::chrono::milliseconds::zero(), false, true, nullptr, reliability);
        } else {
            app->request_event(service, instance, event, {group}, vsomeip::event_type_e::ET_EVENT, reliability);
            app->register_availability_handler(service, instance, [&](vsomeip::service_t, vsomeip::instance_t, bool found) {
                const bool old = available.exchange(found);
                if (found && !old) { ++discoveries; app->subscribe(service, instance, group, 1); }
                if (!found && old) ++losses;
            }, 1, 0);
        }
        std::thread runner([&] { app->start(); });
        const auto end = std::chrono::steady_clock::now() + std::chrono::seconds(seconds);
        std::uint32_t sequence = 0;
        while (std::chrono::steady_clock::now() < end) {
            if (registered && (provider || available)) {
                auto payload = runtime->create_payload();
                payload->set_data(encode(++sequence, static_cast<std::size_t>(bytes)));
                if (provider) app->notify(service, instance, event, payload);
                else {
                    auto request = runtime->create_request(reliable);
                    request->set_service(service); request->set_instance(instance); request->set_method(method);
                    request->set_interface_version(1); request->set_payload(payload);
                    app->send(request); ++requests;
                }
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
        }
        if (provider) app->stop_offer_service(service, instance, 1, 0);
        else { app->unsubscribe(service, instance, group); app->release_service(service, instance); }
        app->stop(); runner.join();
        std::cout << "RESULT {\"role\":\"" << role << "\",\"transport\":\"" << transport
                  << "\",\"requests\":" << requests << ",\"responses\":" << responses
                  << ",\"events\":" << events << ",\"errors\":" << errors << ",\"discoveries\":" << discoveries
                  << ",\"losses\":" << losses << ",\"last_event\":" << last_event << "}" << std::endl;
        return errors == 0 && (provider ? requests >= 10 : responses >= 10 && events >= 10) ? 0 : 1;
    } catch (const std::exception& exc) {
        std::cerr << "ERROR: " << exc.what() << '\n';
        return 2;
    }
}
