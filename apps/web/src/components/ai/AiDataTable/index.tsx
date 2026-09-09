import type { ReactNode } from 'react';
import styles from './index.module.less';

export interface AiDataTableColumn {
  key: string;
  title: string;
}

interface AiDataTableProps {
  columns: AiDataTableColumn[];
  rows: Array<Record<string, ReactNode>>;
}

/** 数据表格（来自 aicss DataTable，去掉品牌示例数据，改为通用列/行驱动）。生产页无数据时不渲染 */
const AiDataTable: React.FC<AiDataTableProps> = ({ columns, rows }) => {
  if (!columns || columns.length === 0 || !rows || rows.length === 0) return null;

  return (
    <div className={styles.tbl}>
      <div className={styles.tblHead} role="row">
        {columns.map((column) => (
          <div key={column.key} className={styles.tblCell} role="columnheader">
            {column.title}
          </div>
        ))}
      </div>
      <div className={styles.tblBody}>
        {rows.map((row, rowIndex) => (
          <div
            key={rowIndex}
            className={styles.tblRow}
            role="row"
            data-testid="data-table-row"
          >
            {columns.map((column) => (
              <div key={column.key} className={styles.tblCell} role="cell">
                {row[column.key]}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
};

export default AiDataTable;
