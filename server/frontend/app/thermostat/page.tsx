import ThermostatDetailPage from "../thermostats/[id]/page";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default function ThermostatPage() {
  return <ThermostatDetailPage params={{ id: "t6pro_living_room" }} />;
}
