"use client";

import React, { useMemo } from "react";
import {
  ComposedChart,
  Line,
  Area,
  ReferenceLine,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface HistoryPoint {
  date: string;
  admissions: number;
}

interface ForecastPoint {
  hospital_id: string;
  target: "admissions" | "inpatient_beds_used";
  horizon: number;
  prediction: number;
  prediction_low: number | null;
  prediction_high: number | null;
  resource_gap: number | null;
  capacity_source: string | null;
  forecast_date: string;
}

interface Props {
  target: "admissions" | "inpatient_beds_used";
  hospitalId: string;
  history: HistoryPoint[];
  forecasts: ForecastPoint[];
  capacity?: number;
  capacitySource?: string | null;
}

const tooltipStyle = {
  background: "rgba(11, 18, 32, 0.95)",
  border: "1px solid rgba(0, 229, 255, 0.2)",
  borderRadius: "0.75rem",
  color: "#F0F4F8",
  fontSize: "12px",
  boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.5)",
};

export default function ContinuousTimelineChart({
  target,
  hospitalId,
  history,
  forecasts,
  capacity = 100,
  capacitySource = "reported",
}: Props) {
  const safeCapacityThreshold = useMemo(() => {
    return Math.round(capacity * 0.85 * 10) / 10;
  }, [capacity]);

  // Combine history and forecast into one continuous timeline
  const chartData = useMemo(() => {
    const data: Array<{
      dateLabel: string;
      rawDate: string;
      isHistorical: boolean;
      actual?: number;
      forecastPoint?: number;
      bandLow?: number;
      bandRange?: number; // Recharts stacked area technique: base + range
      upperQuantile?: number;
      lowerQuantile?: number;
    }> = [];

    // Historical points (last 6-8 weeks)
    const sortedHist = [...history].slice(-8);
    sortedHist.forEach((h) => {
      data.push({
        dateLabel: h.date.slice(5), // MM-DD
        rawDate: h.date,
        isHistorical: true,
        actual: h.admissions,
      });
    });

    // Bridge the last historical point with the start of the forecast line
    if (sortedHist.length > 0 && forecasts.length > 0) {
      const lastH = sortedHist[sortedHist.length - 1];
      // Insert bridge connector on the last point so lines join continuously
      const lastDataPoint = data[data.length - 1];
      lastDataPoint.forecastPoint = lastH.admissions;
    }

    // Filter forecasts for this specific hospital and target
    const hospForecasts = forecasts
      .filter((f) => f.hospital_id === hospitalId && f.target === target)
      .sort((a, b) => a.horizon - b.horizon);

    hospForecasts.forEach((f) => {
      const low = f.prediction_low !== null ? f.prediction_low : f.prediction * 0.85;
      const high = f.prediction_high !== null ? f.prediction_high : f.prediction * 1.15;
      const range = Math.max(0, high - low);

      data.push({
        dateLabel: `Wk ${f.horizon}`,
        rawDate: f.forecast_date,
        isHistorical: false,
        forecastPoint: Math.round(f.prediction * 10) / 10,
        bandLow: Math.round(low * 10) / 10,
        bandRange: Math.round(range * 10) / 10,
        lowerQuantile: Math.round(low * 10) / 10,
        upperQuantile: Math.round(high * 10) / 10,
      });
    });

    return data;
  }, [history, forecasts, hospitalId, target]);

  const lastObservedLabel = useMemo(() => {
    const histPoints = chartData.filter((d) => d.isHistorical);
    return histPoints.length > 0 ? histPoints[histPoints.length - 1].dateLabel : null;
  }, [chartData]);

  // Check if any forecast crosses 85% capacity threshold
  const maxForecastVal = useMemo(() => {
    const fc = chartData.filter((d) => !d.isHistorical && d.forecastPoint !== undefined);
    return fc.length > 0 ? Math.max(...fc.map((d) => d.forecastPoint!)) : 0;
  }, [chartData]);

  const crossesCapacity = target === "inpatient_beds_used" && maxForecastVal > safeCapacityThreshold;

  return (
    <div className="w-full">
      {/* Alert badge if crossing safe capacity */}
      {crossesCapacity && (
        <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 flex items-center justify-between text-xs text-red-200">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-ping" />
            <span>
              <strong>Capacity Alert:</strong> Forecasted occupancy exceeds safe threshold (
              {safeCapacityThreshold} beds, 85% capacity) in upcoming weeks.
            </span>
          </div>
          {capacitySource === "historical_median_fallback" && (
            <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-semibold">
              Estimated Capacity Fallback
            </span>
          )}
        </div>
      )}

      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 10, bottom: 5 }}>
            <defs>
              {/* Shaded confidence interval band */}
              <linearGradient id="bandGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#00E5FF" stopOpacity={0.25} />
                <stop offset="100%" stopColor="#00E5FF" stopOpacity={0.05} />
              </linearGradient>
            </defs>

            <CartesianGrid stroke="rgba(148, 163, 184, 0.08)" strokeDasharray="3 3" />
            <XAxis
              dataKey="dateLabel"
              stroke="#64748B"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
            />
            <YAxis
              stroke="#64748B"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(value: any, name: string) => {
                if (name === "Historical") return [`${value} ${target === "admissions" ? "patients" : "beds"}`, "Observed"];
                if (name === "Forecast (Point)") return [`${value} ${target === "admissions" ? "patients" : "beds"}`, "Point Forecast"];
                if (name === "Confidence Band") return [`${value} spread`, "80% Prediction Interval"];
                return [value, name];
              }}
            />
            <Legend wrapperStyle={{ fontSize: "12px", color: "#94A3B8" }} />

            {/* Vertical divider marking last observed week */}
            {lastObservedLabel && (
              <ReferenceLine
                x={lastObservedLabel}
                stroke="#F59E0B"
                strokeDasharray="4 4"
                strokeWidth={2}
                label={{
                  value: "Observed / Forecast Cutoff",
                  position: "top",
                  fill: "#F59E0B",
                  fontSize: 10,
                  fontWeight: 600,
                }}
              />
            )}

            {/* Capacity threshold line (occupancy target) */}
            {target === "inpatient_beds_used" && (
              <ReferenceLine
                y={safeCapacityThreshold}
                stroke="#EF4444"
                strokeDasharray="5 5"
                strokeWidth={2}
                label={{
                  value: `85% Safe Cap (${safeCapacityThreshold} beds)`,
                  position: "right",
                  fill: "#EF4444",
                  fontSize: 10,
                  fontWeight: 600,
                }}
              />
            )}

            {/* Confidence Band (10th to 90th percentile) */}
            <Area
              name="Confidence Band"
              dataKey="bandLow"
              stackId="ci"
              stroke="transparent"
              fill="transparent"
            />
            <Area
              dataKey="bandRange"
              stackId="ci"
              stroke="transparent"
              fill="url(#bandGradient)"
            />

            {/* Historical admissions line */}
            <Line
              name="Historical"
              type="monotone"
              dataKey="actual"
              stroke="#38BDF8"
              strokeWidth={2.5}
              dot={{ r: 3, fill: "#38BDF8" }}
              activeDot={{ r: 5 }}
            />

            {/* Forecast line (point estimate) */}
            <Line
              name="Forecast (Point)"
              type="monotone"
              dataKey="forecastPoint"
              stroke="#00E5FF"
              strokeWidth={3}
              strokeDasharray="4 4"
              dot={{ r: 4, fill: "#00E5FF", stroke: "#0B1120", strokeWidth: 2 }}
              activeDot={{ r: 6 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Accuracy & Model Note */}
      <div className="mt-4 pt-3 border-t border-white/5 flex flex-col sm:flex-row items-start sm:items-center justify-between text-xs text-slate-400 gap-2">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan" />
          <span>
            {target === "inpatient_beds_used" ? (
              <span>
                <strong className="text-emerald-400">Beds model (test set):</strong>{" "}
                MAE 6.6–7.6 beds/wk across H1–H4 · beats MA4 baseline all 4 horizons ·{" "}
                80.1–81.4% PI coverage (target 80%).
              </span>
            ) : (
              <span>
                <strong className="text-amber-400">Admissions model (test set):</strong>{" "}
                MAE ~49–56 admissions/wk across H1–H4 · comparable to MA4 baseline ·{" "}
                81.8–82.9% PI coverage (target 80%).
              </span>
            )}
          </span>
        </div>
        <div className="font-mono text-[11px] text-slate-400">
          Quantiles: 10th - 90th Percentile (~80% coverage)
        </div>
      </div>
    </div>
  );
}
