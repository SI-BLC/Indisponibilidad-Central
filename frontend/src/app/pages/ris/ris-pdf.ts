import jsPDF from 'jspdf';

const MARGIN = 12;
const PW = 210;
const PH = 297;
const CW = PW - MARGIN * 2;
const HEADER_H = 16;
const FOOTER_H = 10;
const CONTENT_TOP = MARGIN + HEADER_H;
const CONTENT_BOT = PH - FOOTER_H;
const GAP = 2;

const COL_BLC_RED: [number, number, number] = [192, 57, 43];
const COL_BLC_BLUE: [number, number, number] = [43, 143, 212];
const COL_DARK_BG: [number, number, number] = [30, 32, 40];
const LOGO_RATIO = 5929 / 1251;
const MESES_NOMBRE = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

function fmtMes(mes: string): string {
  const [a, m] = mes.split('-');
  return `${MESES_NOMBRE[+m]} ${a}`;
}

function parseRgb(css: string): [number, number, number] {
  const m = css.match(/(\d+)/g);
  if (m && m.length >= 3) return [+m[0], +m[1], +m[2]];
  return [255, 255, 255];
}

function isLightColor(r: number, g: number, b: number): boolean {
  return (r * 299 + g * 587 + b * 114) / 1000 > 128;
}

// ─── Cover (same layout, colors vary) ───────────────────────────────────────
function drawCover(doc: jsPDF, r: any, assets: RisPdfAssets, light: boolean) {
  const bg: [number, number, number] = light ? [255, 255, 255] : COL_DARK_BG;
  const titleCol: [number, number, number] = light ? [26, 26, 26] : [255, 255, 255];
  const subCol: [number, number, number] = light ? [80, 85, 100] : [180, 185, 200];
  const mutedCol: [number, number, number] = light ? [120, 125, 140] : [140, 145, 160];
  const footerCol: [number, number, number] = light ? [160, 165, 175] : [80, 85, 95];

  doc.setFillColor(...bg);
  doc.rect(0, 0, PW, PH, 'F');

  if (assets.logo) {
    const logoH = 10;
    doc.addImage(assets.logo, 'PNG', 25, 25, logoH * LOGO_RATIO, logoH);
  }

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(9);
  doc.setTextColor(...COL_BLC_RED);
  doc.text('PRODUCCIÓN DE ENERGÍA', 25, 148);

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(24);
  doc.setTextColor(...titleCol);
  doc.text('Monitorización, Control y', 25, 165);
  doc.text('Gestión de activos', 25, 178);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(12);
  doc.setTextColor(...subCol);
  doc.text(r.central.nemo, 25, 195);
  doc.setFontSize(11);
  doc.setTextColor(...mutedCol);
  doc.text(fmtMes(r.mes), 25, 203);

  // Icon row
  const iconSize = 14;
  const iconY = 240;
  const iconSpacing = 160 / 5;
  assets.icons.forEach((img, i) => {
    if (!img) return;
    const ix = 25 + iconSpacing * i + (iconSpacing - iconSize) / 2;
    doc.addImage(img, 'PNG', ix, iconY, iconSize, iconSize);
  });

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(7);
  doc.setTextColor(...subCol);
  doc.text('REPORTE OFICIAL', 25, 268);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(5.5);
  doc.setTextColor(...mutedCol);
  doc.text('SISTEMA DE GENERACIÓN', 25, 272);
  doc.text('DE ENERGÍA ELÉCTRICA', 25, 276);

  doc.setFontSize(5.5);
  doc.setTextColor(...footerCol);
  doc.text(`© ${new Date().getFullYear()} BLC POWER GENERATION`, 25, 282);
}

// ─── Back cover (same layout, no dynamic texts) ─────────────────────────────
function drawBackCover(doc: jsPDF, assets: RisPdfAssets, light: boolean) {
  doc.addPage();
  const bg: [number, number, number] = light ? [255, 255, 255] : COL_DARK_BG;
  const titleCol: [number, number, number] = light ? [26, 26, 26] : [255, 255, 255];
  const subCol: [number, number, number] = light ? [80, 85, 100] : [180, 185, 200];
  const mutedCol: [number, number, number] = light ? [120, 125, 140] : [140, 145, 160];
  const footerCol: [number, number, number] = light ? [160, 165, 175] : [80, 85, 95];

  doc.setFillColor(...bg);
  doc.rect(0, 0, PW, PH, 'F');

  if (assets.logo) {
    const logoH = 10;
    doc.addImage(assets.logo, 'PNG', 25, 25, logoH * LOGO_RATIO, logoH);
  }

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(9);
  doc.setTextColor(...COL_BLC_RED);
  doc.text('PRODUCCIÓN DE ENERGÍA', 25, 148);

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(24);
  doc.setTextColor(...titleCol);
  doc.text('Monitorización, Control y', 25, 165);
  doc.text('Gestión de activos', 25, 178);

  const iconSize = 14;
  const iconY = 240;
  const iconSpacing = 160 / 5;
  assets.icons.forEach((img, i) => {
    if (!img) return;
    const ix = 25 + iconSpacing * i + (iconSpacing - iconSize) / 2;
    doc.addImage(img, 'PNG', ix, iconY, iconSize, iconSize);
  });

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(7);
  doc.setTextColor(...subCol);
  doc.text('REPORTE OFICIAL', 25, 268);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(5.5);
  doc.setTextColor(...mutedCol);
  doc.text('SISTEMA DE GENERACIÓN', 25, 272);
  doc.text('DE ENERGÍA ELÉCTRICA', 25, 276);

  doc.setFontSize(5.5);
  doc.setTextColor(...footerCol);
  doc.text(`© ${new Date().getFullYear()} BLC POWER GENERATION`, 25, 282);
}

// ─── Page header / banner / footer ──────────────────────────────────────────
function drawHeader(doc: jsPDF, logoImg: string | null, light: boolean) {
  if (logoImg) {
    const logoH = 8;
    doc.addImage(logoImg, 'PNG', MARGIN, MARGIN, logoH * LOGO_RATIO, logoH);
  }
  const dateStr = new Date().toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' });
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(light ? 120 : 180, light ? 125 : 180, light ? 140 : 190);
  doc.text(dateStr, PW - MARGIN, MARGIN + 5, { align: 'right' });
  const lc = light ? [200, 205, 215] : [60, 65, 80];
  doc.setDrawColor(lc[0], lc[1], lc[2]);
  doc.setLineWidth(0.3);
  doc.line(MARGIN, MARGIN + HEADER_H - 3, PW - MARGIN, MARGIN + HEADER_H - 3);
}

function drawTitleBanner(doc: jsPDF, r: any, y: number): number {
  const bannerH = 14;
  doc.setFillColor(...COL_BLC_BLUE);
  doc.roundedRect(MARGIN, y, CW, bannerH, 2, 2, 'F');
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(12);
  doc.setTextColor(255, 255, 255);
  doc.text(r.central.nemo, MARGIN + 6, y + 6);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  doc.text(`—  ${fmtMes(r.mes)}`, MARGIN + 6 + doc.getTextWidth(r.central.nemo + '  '), y + 6);
  doc.setFontSize(8);
  doc.setTextColor(220, 230, 255);
  doc.text('Reporte de Indisponibilidad de Soporte', MARGIN + 6, y + 11.5);
  return y + bannerH + GAP;
}

function drawFooter(doc: jsPDF, pageNum: number, totalPages: number, light: boolean) {
  const c = light ? [140, 140, 140] : [180, 180, 180];
  doc.setFontSize(7.5);
  doc.setTextColor(c[0], c[1], c[2]);
  doc.text(`RIS — ${new Date().toLocaleDateString('es-AR')}`, MARGIN, PH - 5);
  doc.text(`${pageNum} / ${totalPages}`, PW - MARGIN, PH - 5, { align: 'right' });
}

// ─── Types & assets ─────────────────────────────────────────────────────────
export interface SectionCapture {
  dataUrl: string;
  width: number;
  height: number;
}

export interface RisPdfAssets {
  logo: string | null;
  icons: (string | null)[];
}

export async function loadPdfAssets(): Promise<RisPdfAssets> {
  const load = async (path: string): Promise<string | null> => {
    try {
      const resp = await fetch(path);
      if (!resp.ok) return null;
      const blob = await resp.blob();
      return new Promise(resolve => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = () => resolve(null);
        reader.readAsDataURL(blob);
      });
    } catch { return null; }
  };
  const [logo, ...icons] = await Promise.all([
    load('assets/images/01-BLC_POWER_POSITIVO.png'),
    load('assets/images/ris-icon-1.png'),
    load('assets/images/ris-icon-2.png'),
    load('assets/images/ris-icon-3.png'),
    load('assets/images/ris-icon-4.png'),
    load('assets/images/ris-icon-5.png'),
  ]);
  return { logo, icons };
}

// ─── Main generator ─────────────────────────────────────────────────────────
export function generateRisPdf(r: any, sections: SectionCapture[], assets: RisPdfAssets, bgColor: string, pageBreaks?: Set<number>) {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const bgRgb = parseRgb(bgColor);
  const lightBg = isLightColor(...bgRgb);

  drawCover(doc, r, assets, lightBg);

  // ═══ CONTENT PAGES ═══
  const BANNER_H = 14 + GAP;

  interface PlacedItem { pageIdx: number; y: number; h: number; secIdx: number }
  const placed: PlacedItem[] = [];
  let pageIdx = 0;
  let y = CONTENT_TOP + BANNER_H;

  for (let i = 0; i < sections.length; i++) {
    const sec = sections[i];
    const imgH = (sec.height / sec.width) * CW;
    const available = CONTENT_BOT - y;

    const forceBreak = pageBreaks?.has(i) && placed.some(p => p.pageIdx === pageIdx);
    if (forceBreak || (imgH > available && placed.some(p => p.pageIdx === pageIdx))) {
      pageIdx++;
      y = CONTENT_TOP;
    }

    placed.push({ pageIdx, y, h: imgH, secIdx: i });
    y += imgH + GAP;
  }

  const totalContentPages = pageIdx + 1;

  for (let p = 0; p < totalContentPages; p++) {
    doc.addPage();
    doc.setFillColor(...bgRgb);
    doc.rect(0, 0, PW, PH, 'F');

    drawHeader(doc, assets.logo, lightBg);

    if (p === 0) {
      drawTitleBanner(doc, r, CONTENT_TOP);
    }

    const pageSections = placed.filter(pi => pi.pageIdx === p);
    for (const { y: sy, h, secIdx } of pageSections) {
      doc.addImage(sections[secIdx].dataUrl, 'PNG', MARGIN, sy, CW, h);
    }
  }

  drawBackCover(doc, assets, lightBg);

  // ═══ FOOTERS ═══
  const total = doc.getNumberOfPages();
  const contentPages = total - 2;
  for (let p = 2; p <= total - 1; p++) {
    doc.setPage(p);
    drawFooter(doc, p - 1, contentPages, lightBg);
  }

  doc.save(`RIS_${r.central.nemo}_${r.mes}.pdf`);
}
