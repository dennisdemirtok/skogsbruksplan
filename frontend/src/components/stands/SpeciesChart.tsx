import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';

interface SpeciesChartProps {
  pine: number;
  spruce: number;
  deciduous: number;
  contorta: number;
}

const SPECIES_COLORS: Record<string, string> = {
  Tall: '#d97706',      // amber
  Gran: '#15803d',      // dark green
  Löv: '#84cc16',       // lime
  Contorta: '#0d9488',  // teal
};

export default function SpeciesChart({ pine, spruce, deciduous, contorta }: SpeciesChartProps) {
  const data = [
    { name: 'Tall', value: pine },
    { name: 'Gran', value: spruce },
    { name: 'Löv', value: deciduous },
    { name: 'Contorta', value: contorta },
  ].filter((d) => d.value > 0);

  if (data.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-gray-400">
        Ingen trädslags-data
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={180}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={40}
          outerRadius={65}
          paddingAngle={2}
          dataKey="value"
          label={({ name, value }) => `${name} ${value}%`}
          labelLine={false}
        >
          {data.map((entry) => (
            <Cell key={entry.name} fill={SPECIES_COLORS[entry.name]} />
          ))}
        </Pie>
        <Tooltip
          formatter={(value: number) => [`${value}%`, '']}
          contentStyle={{
            borderRadius: '8px',
            border: '1px solid #e5e7eb',
            fontSize: '12px',
          }}
        />
        <Legend
          iconType="circle"
          iconSize={8}
          wrapperStyle={{ fontSize: '12px' }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
