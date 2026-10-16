export interface SettingsResponse {
  busqueda: {
    terminos: string[];
    ubicaciones: string[];
    filtros_exclusion: string[];
    antiguedad_horas: number;
    limite_por_fuente: number;
  };
  fuentes: Record<string, any>;
  evaluacion: {
    umbral_minimo_puntuacion: number;
    generar_documentos: boolean;
    idioma_documentos: string;
  };
  notificaciones: {
    guardar_en_interfaz: boolean;
    enviar_telegram: boolean;
    telegram?: {
      habilitado: boolean;
      adjuntar_documentos: boolean;
      notificar_solo_superan_umbral: boolean;
      notificar_resumen_vacio: boolean;
    };
  };
  horario: {
    hora: number;
    minuto: number;
  };
  secrets_status: {
    telegram_configured: boolean;
    infojobs_configured: boolean;
  };
  privacy_notice: {
    telegram_transmission_note: string;
  };
}
